import logging
import re
import uuid
from dataclasses import dataclass
from uuid import UUID

from future.backports.datetime import datetime
from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import func
from weaviate.classes.query import Filter

from internal.core.file_extractor import FileExtractor
from internal.entity.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED
from internal.entity.dataset_entity import DocumentStatus, SegmentStatus
from internal.exception import NotFoundException
from internal.lib.helper import generate_text_hash
from internal.model import Document, Segment, KeywordTable, DatasetQuery
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .embeddings_service import EmbeddingsService
from .jieba_service import JiebaService
from .keyword_table_service import KeywordTableService
from .process_rule_service import ProcessRuleService
from .vector_db_service import VectorDatabaseService


@inject
@dataclass
class IndexingService(BaseService):
    """索引构建服务"""
    db: SQLAlchemy
    redis_client: Redis
    file_extractor: FileExtractor
    process_rule_service: ProcessRuleService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    keyword_table_service: KeywordTableService
    vector_database_service: VectorDatabaseService

    def build_documents(self, document_ids: list[UUID]) -> None:
        """根据文档Ids列表构建知识库文档，包含：加载，分割，索引构建，数据存储等内容"""
        # 1. 获取文档列表
        documents = self.db.session.query(Document).filter(
            Document.id.in_(document_ids)
        ).all()

        # 2. 循环处理文件
        for document in documents:
            try:
                self.update(document, status=DocumentStatus.PARSING, processing_started_at=datetime.now())

                # 1.加载文档
                lc_documents = self._parsing(document)

                # 2.分割文档
                lc_segments = self._splitting(document, lc_documents)

                # 3.索引文档
                self._indexing(document, lc_segments)

                # 4. 存储操作，状态更新，微量数据库的存储
                self._completed(document, lc_segments)

            except Exception as e:
                logging.exception(f"构建文档发生错误，错误信息：{str(e)}")
                self.update(
                    document,
                    status=DocumentStatus.ERROR,
                    error=str(e),
                    stopped_at=datetime.now()
                )

    def update_document_enabled(self, document_id: UUID) -> None:
        """更新文档启用状态"""
        # 1. 构建缓存键
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document_id)

        # 2. 根据传递的document_id获取文档列表
        document: Document = self.get(Document, document_id)
        if document is None:
            logging.exception(f"当前文档不存在，文档id: {document_id}")
            raise NotFoundException("当前文档不存在")
        # 3. 查询归属于当前文件的甩片段的节点Id
        segments = self.db.session.query(Segment).with_entities(
            Segment.id, Segment.node_id, Segment.enabled
        ).filter(
            Segment.document_id == document_id,
            Segment.status == SegmentStatus.COMPLETED
        ).all()

        segment_ids = [id for id, _, _ in segments]
        node_ids = [node_id for _, node_id, _ in segments]

        try:
            # 4. 执行循环遍历所有的node_ids并更新向量数据库
            collection = self.vector_database_service.collection
            for node_id in node_ids:
                try:
                    collection.data.update(
                        uuid=node_id,
                        properties={
                            "document_enabled": document.enabled
                        }
                    )
                except Exception as e:
                    with self.db.auto_commit():
                        self.db.session.query(Segment).filter(
                            Segment.node_id == node_id
                        ).update({
                            "error": str(e),
                            "status": SegmentStatus.ERROR,
                            "enabled": False,
                            "disabled_at": datetime.now(),
                            "stopped_at": datetime.now()
                        })
                # 5. 更新关键词对应的数据（enable为false表示从关键词中删除数据，enable为true表示向关键词表增加数据）
                if document.enabled is True:
                    # 6. 从禁用改为启用，增加关键词
                    enabled_segment_ids = [id for id, _, enabled in segments if enabled is True]
                    self.keyword_table_service.add_keyword_table_form_ids(document.dataset_id, enabled_segment_ids)
                else:
                    self.keyword_table_service.delete_keyword_table_from_ids(document.dataset_id, segment_ids)
        except Exception as e:
            # 5. 处理日志并将状态修改回原来的状态
            logging.exception(f"修改向量数据库文档启用状态失败，文档id: {document_id}，错误信息：{str(e)}")
            origin_enabled = not document.enabled
            self.update(
                document,
                enabled=origin_enabled,
                disabled_at=None if origin_enabled else datetime.now()
            )
        finally:
            # 6. 清空redis中的锁
            self.redis_client.delete(cache_key)

    def delete_document(self, dataset_id: UUID, document_id: UUID) -> None:
        """根据知识库Id+文档Id删除文档相关数据"""
        # 1. 查找该文档下的所有片段Id列表
        segments_ids = [
            str(id) for id, in self.db.session.query(Segment).with_entities(Segment.id).filter(
                Segment.document_id == document_id
            ).all()
        ]

        # 2. 调用向量数据库删除其相关记录
        collection = self.vector_database_service.collection
        collection.data.delete_many(
            where=Filter.by_property("document_id").equal(document_id)
        )

        # 3. 删除postgres关联的segment记录
        with self.db.auto_commit():
            self.db.session.query(Segment).filter(
                Segment.document_id == document_id
            ).delete()

        # 4. 删除片段Id对应的关键词记录
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, segments_ids)

    def delete_dataset(self, dataset_id: UUID) -> None:
        """删除知识库"""
        try:
            with self.db.auto_commit():
                # 1. 删除关联的文档记录
                self.db.session.query(Document).filter(
                    Document.dataset_id == dataset_id
                ).delete()
                # 2. 删除关联片段
                self.db.session.query(Segment).filter(
                    Segment.dataset_id == dataset_id
                ).delete()
                # 3.删除关联关键词
                self.db.session.query(KeywordTable).filter(
                    KeywordTable.dataset_id == dataset_id
                ).delete()
                # 4. 删除关联查询记录
                self.db.session.query(DatasetQuery).filter(
                    DatasetQuery.dataset_id == dataset_id
                ).delete()
                # 5. 删除关联向量数据库
                self.vector_database_service.collection.data.delete_many(
                    where=Filter.by_property("dataset_id").equal(dataset_id)
                )

        except Exception as e:
            logging.exception(f"异步删除知识库关联内容出错：dataset_id: {dataset_id}, 错误信息：{str(e)}")

    def _parsing(self, document: Document) -> list[LCDocument]:
        """解析文件为langchain文档列表类"""
        upload_file = document.upload_file
        lc_documents = self.file_extractor.load(upload_file, False, True)

        # 2. 循环处理langchain文档，并删除多余的空白字符串
        for lc_document in lc_documents:
            lc_document.page_content = self._clean_extra_text(lc_document.page_content)

        # 3. 更新文档状态并记录时间
        self.update(
            document,
            character_count=sum([len(lc_doc.page_content) for lc_doc in lc_documents]),
            status=DocumentStatus.SPLITTING,
            parsing_completed_at=datetime.now()
        )

        return lc_documents

    def _splitting(self, document: Document, lc_documents: list[LCDocument]) -> list[LCDocument]:
        """文档分割，拆分成小块片段"""
        # 1. 根据process_rule分割文档
        process_rule = document.process_rule

        text_splitter = self.process_rule_service.get_text_splitter_by_process_rule(
            process_rule,
            self.embeddings_service.calculate_token_count
        )

        # 2. 按照process_rule规则清除多余的字符串
        for lc_document in lc_documents:
            lc_document.page_content = self.process_rule_service.clean_text_process_rule(
                lc_document.page_content,
                process_rule
            )
        # 3. 分割文档列表为片段列表
        lc_segments = text_splitter.split_documents(lc_documents)

        # 4. 获取对应文档下最大片段位置
        position = self.db.session.query(func.coalesce(func.max(Segment.position), 10)).filter(
            Segment.document_id == document.id
        ).scalar()

        # 5. 循环处理片段数据并添加元数据，同时存储到postgres数据库
        segments = []
        for lc_segment in lc_segments:
            position += 1
            content = lc_segment.page_content
            segment = self.create(
                Segment,
                account_id=document.account_id,
                dataset_id=document.dataset_id,
                document_id=document.id,
                node_id=uuid.uuid4(),
                position=position,
                content=content,
                character_count=len(content),
                token_count=self.embeddings_service.calculate_token_count(content),
                hash=generate_text_hash(content),
                status=SegmentStatus.WAITING
            )
            lc_segment.metadata = {
                "account_id": str(document.account_id),
                "dataset_id": str(document.dataset_id),
                "document_id": str(document.id),
                "segment_id": str(segment.id),
                "node_id": str(segment.node_id),
                "document_enabled": False,
                "segment_enabled": False
            }
            segments.append(segment)
        # 6. 更新文档的数据
        self.update(
            document,
            token_count=sum([segment.token_count for segment in segments]),
            status=DocumentStatus.INDEXING,
            splitting_completed_at=datetime.now()
        )
        return lc_segments

    def _indexing(self, document: Document, lc_segments: list[LCDocument]):
        """索引文档信息，包含：关键词提取，词表构建"""
        for lc_segment in lc_segments:
            # 1. 提取每个片段的关键词，关键词最多不能超过10个
            keywords = self.jieba_service.extract_keywords(lc_segment.page_content, 10)

            # 2. 逐条更新文档片段中的关键词
            self.db.session.query(Segment).filter(
                Segment.id == lc_segment.metadata["segment_id"]
            ).update({
                "keywords": keywords,
                "status": SegmentStatus.INDEXING,
                "indexing_completed_at": datetime.now()
            })

            # 3. 获取当前知识库的关键词表
            keyword_table_record = self.keyword_table_service.get_keyword_table_from_dataset_id(document.dataset_id)
            keyword_table = {
                field: set(value) for field, value in keyword_table_record.keyword_table.items()
            }

            # 4. 循环将新关键词添加到关键词表中
            for keyword in keywords:
                if keyword not in keyword_table:
                    keyword_table[keyword] = set()
                keyword_table[keyword].add(lc_segment.metadata["segment_id"])

            # 5. 更新关键词表
            self.update(
                keyword_table_record,
                keyword_table={field: list(value) for field, value in keyword_table.items()}
            )
        self.update(
            document,
            indexing_completed_at=datetime.now()
        )

    def _completed(self, document: Document, lc_segments: list[LCDocument]) -> None:
        """存储文档片段到向量数据库，并完成状态更新"""
        for lc_segment in lc_segments:
            lc_segment.metadata["document_enabled"] = True
            lc_segment.metadata["segment_enabled"] = True
        try:
            for i in range(0, len(lc_segments), 10):
                chunks = lc_segments[i:i + 10]
                ids = [chunk.metadata["node_id"] for chunk in chunks]
                self.vector_database_service.vector_store.add_documents(
                    chunks, ids=ids
                )
                with self.db.auto_commit():
                    self.db.session.query(Segment).filter(
                        Segment.node_id.in_(ids)
                    ).update({
                        "status": SegmentStatus.COMPLETED,
                        "completed_at": datetime.now(),
                        "enabled": True
                    })
        except Exception as e:
            logging.exception("构建文档片段索引发生异常，异常信息：%(error)s", {"error": e})
            with self.db.auto_commit():
                self.db.session.query(Segment).filter(
                    Segment.node_id.in_(ids)
                ).update({
                    "status": SegmentStatus.ERROR,
                    "completed_at": None,
                    "stopped_at": datetime.now(),
                    "enabled": False
                })

        self.update(
            document,
            status=DocumentStatus.COMPLETED,
            completed_at=datetime.now(),
            enabled=True
        )

    @classmethod
    def _clean_extra_text(cls, text: str) -> str:
        """清除过滤传递的多余空白字符串"""
        text = re.sub(r'<\|', '<', text)
        text = re.sub(r'\|>', '>', text)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F\xEF\xBF\xBE]', '', text)
        text = re.sub('\uFFFE', '', text)  # 删除零宽非标记字符
        return text
