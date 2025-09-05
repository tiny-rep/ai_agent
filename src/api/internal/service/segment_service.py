import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from injector import inject
from langchain_core.documents import Document as LCDocument
from redis import Redis
from sqlalchemy import func, asc

from internal.schema.segment_schema import CreateSegmentReq, UpdateSegmentReq, GetSegmentsWithPageReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .embeddings_service import EmbeddingsService
from .jieba_service import JiebaService
from .keyword_table_service import KeywordTableService
from .vector_db_service import VectorDatabaseService
from ..entity.cache_entity import LOCK_SEGMENT_UPDATE_ENABLED, LOCK_EXPIRE_TIME
from ..entity.dataset_entity import DocumentStatus, SegmentStatus
from ..exception import ValidateErrorException, NotFoundException, FailException
from ..lib.helper import generate_text_hash
from ..model import Document, Segment, Account


@inject
@dataclass
class SegmentService(BaseService):
    """文档片段处理服务"""
    db: SQLAlchemy
    redis_client: Redis
    jieba_service: JiebaService
    embedding_service: EmbeddingsService
    keyword_table_service: KeywordTableService
    vector_database_service: VectorDatabaseService

    def create_segment(self, dataset_id: UUID, document_id: UUID, req: CreateSegmentReq, account: Account):
        """创建文档片段"""
        account_id = str(account.id)

        # 1 校验token长度不能超过1000
        token_count = self.vector_database_service.embeddings_service.calculate_token_count(req.content.data)
        if token_count > 1000:
            raise ValidateErrorException("片段内容的长度不能超过1000 token")

        # 2.验证文档信息有效性
        document: Document = self.get(Document, document_id)
        if (
                document is None
                or str(document.account_id) != account_id
                or document.dataset_id != dataset_id
        ):
            raise NotFoundException("该知识库文档不存在，或无权限新增")

        # 3.判断文档的状态是否可以新增片段数据，只有completed才可以新增
        if document.status != DocumentStatus.COMPLETED:
            raise FailException("当前文档不可新增片段，请稍后重试")

        # 4.提取文档片段的最大位置
        position = self.db.session.query(func.coalesce(func.max(Segment.position), 0)).filter(
            Segment.document_id == document_id
        ).scalar()

        # 5.检测是否传递了keywords，如果没有，通过jieba服务生成
        if req.keywords.data is None or len(req.keywords.data) == 0:
            req.keywords.data = self.jieba_service.extract_keywords(req.content.data, 10)

        # 6.写入到postgres
        segment = None
        try:
            # 7.位置+1
            position += 1
            segment = self.create(
                Segment,
                account_id=account_id,
                dataset_id=dataset_id,
                document_id=document_id,
                node_id=uuid.uuid4(),
                position=position,
                content=req.content.data,
                character_count=len(req.content.data),
                token_count=token_count,
                keywords=req.keywords.data,
                hash=generate_text_hash(req.content.data),
                enabled=True,
                processing_started_at=datetime.now(),
                indexing_completed_at=datetime.now(),
                completed_at=datetime.now(),
                status=SegmentStatus.COMPLETED,
            )
            # 8.写入到向量数据库
            self.vector_database_service.vector_store.add_documents(
                [LCDocument(
                    page_content=req.content.data,
                    metadata={
                        "account_id": str(document.account_id),
                        "dataset_id": str(document.dataset_id),
                        "document_id": str(document.id),
                        "segment_id": str(segment.id),
                        "node_id": str(segment.node_id),
                        "document_enabled": document.enabled,
                        "segment_enabled": True
                    }
                )],
                ids=[str(segment.node_id)]
            )
            # 9. 重新计算片段的字符总数以及token总数
            document_character_count, document_token_count = self.db.session.query(
                func.coalesce(func.sum(Segment.character_count), 0),
                func.coalesce(func.sum(Segment.token_count), 0)
            ).filter(Segment.document_id == document_id).first()

            # 10. 更新文档对应的信息
            self.update(
                document,
                character_count=document_character_count,
                token_count=document_token_count
            )
            # 11. 更新关键词表信息
            if document.enabled is True:
                self.keyword_table_service.add_keyword_table_form_ids(dataset_id, [segment.id])
        except Exception as e:
            logging.exception(f"新增文档片段内容发生异常，错误信息：{str(e)}")
            if segment:
                self.update(
                    segment,
                    error=str(e),
                    status=SegmentStatus.ERROR,
                    enabled=False,
                    disabled_at=datetime.now(),
                    stopped_at=datetime.now()
                )
            raise FailException("新增文档片段失败，请稍后尝试")

    def update_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID, req: UpdateSegmentReq,
                       account: Account) -> Segment:
        """更新文档片段"""
        account_id = str(account.id)
        # 1.获取片段信息并校验
        segment: Segment = self.get(Segment, segment_id)
        if (
                segment is None
                or str(segment.account_id) != account_id
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
        ):
            raise NotFoundException("该文档片段不存在，或无权限修改")
        # 2.判断文档片段是否牌可修改的状态
        if segment.status != SegmentStatus.COMPLETED:
            raise FailException("当前片段不可修改状态，请稍后重试")
        # 3.检测是否传递了keywords，如果没有传递，利用Jieba生成
        if req.keywords.data is None or len(req.keywords.data) == 0:
            req.keywords.data = self.jieba_service.extract_keywords(req.content.data)
        # 4.计算内容hash值，用于判断是否需要更新向量数据库及文档详情
        new_hash = generate_text_hash(req.content.data)
        required_update = segment.hash != new_hash
        try:
            # 5.更新segment记录
            self.update(
                segment,
                keywords=req.keywords.data,
                content=req.content.data,
                hash=new_hash,
                character_count=len(req.content.data),
                token_count=self.embedding_service.calculate_token_count(req.content.data)
            )
            # 6.更新片段归属关键词信息
            self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id])
            self.keyword_table_service.add_keyword_table_form_ids(dataset_id, [segment_id])
            # 7.检测是否需要更新文档信息以及向量数据库
            if required_update:
                # 8.更新文档信息，包含：字符总数，token总数
                document = segment.document
                document_character_count, document_token_count = self.db.session.query(
                    func.coalesce(func.sum(Segment.character_count), 0),
                    func.coalesce(func.sum(Segment.token_count), 0)
                ).filter(Segment.document_id == document_id).first()
                self.update(
                    document,
                    character_count=document_character_count,
                    token_count=document_token_count
                )
                # 9.更新向量数据库
                self.vector_database_service.collection.data.update(
                    uuid=str(segment.node_id),
                    properties={
                        "text": req.content.data
                    },
                    vector=self.embedding_service.embeddings.embed_query(req.content.data)
                )
        except Exception as e:
            logging.exception(f"更新文档片段内容发生异常，错误信息：{str(e)}")
            raise FailException("更新文档片段失败，请稍后尝试")

    def get_segments_with_page(self,
                               dataset_id: UUID, document_id: UUID, req: GetSegmentsWithPageReq, account: Account) \
            -> tuple[list[Segment], Paginator]:
        """分页查询文档片段信息"""

        account_id = str(account.id)

        # 1. 获取文档并校验权限
        document: Document = self.get(Document, document_id)
        if document is None or document.dataset_id != dataset_id or str(document.account_id) != account_id:
            raise NotFoundException("该文档不存在，或者无权限查询")
        # 2. 构建分页器
        paginator = Paginator(db=self.db, req=req)
        # 3. 构建筛选器
        filters = [Segment.document_id == document_id]
        if req.search_word.data:
            filters.append(Segment.content.ilike(f'%{req.search_word.data}%'))
        # 4. 执行分页
        segments = paginator.paginate(
            self.db.session.query(Segment).filter(*filters).order_by(asc("position"))
        )
        return segments, paginator

    def get_segment(self, dataset_id: UUID, document_id: UUID, segment_id: UUID, account: Account) -> Segment:
        """获取片段详细信息"""
        account_id = str(account.id)
        # 1.获取片段信息并校验
        segment: Segment = self.get(Segment, segment_id)
        if (
                segment is None
                or str(segment.account_id) != account_id
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
        ):
            raise NotFoundException("该文档片段不存在")
        return segment

    def update_segment_enabled(self,
                               dataset_id: UUID, document_id: UUID, segment_id: UUID, enabled: bool,
                               account: Account) -> Segment:
        """更新文档片段启用状态"""
        account_id = str(account.id)
        # 1. 校验文档片段的权限
        segment: Segment = self.get(Segment, segment_id)
        if (
                segment is None
                or str(segment.account_id) != account_id
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
        ):
            raise NotFoundException("该文档片段不存在，或无权限修改")
        # 2. 判断文档片段是否处于可用状态
        if segment.status != SegmentStatus.COMPLETED:
            raise FailException("当前片段不可修改状态，请稍后重试")
        # 3. 判断更新的片段启用状态是否与数据库一致
        if enabled == segment.enabled:
            raise FailException(f"片段状态修改错误，当前已是{'启用' if enabled else '禁用'}状态")
        # 4. 获取更新片段启用状态锁并上锁定检测
        cache_key = LOCK_SEGMENT_UPDATE_ENABLED.format(segment_id=segment_id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            raise FailException("当前文档片段正在修改状态，请稍后重试")
        # 5. 上锁并更新对应的数据，包含：pg记录，向量数据，关键词表
        with self.redis_client.lock(cache_key, LOCK_EXPIRE_TIME):
            try:
                # 6. 更新postgres
                self.update(
                    segment,
                    enabled=enabled,
                    disabled_at=None if enabled else datetime.now()
                )
                # 7. 更新关键词表
                document = segment.document
                if enabled is True and document.enabled is True:
                    self.keyword_table_service.add_keyword_table_form_ids(dataset_id, [segment_id])
                else:
                    self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id])
                # 8. 更新微量数据库
                self.vector_database_service.collection.data.update(
                    uuid=segment.node_id,
                    properties={
                        "segment_enabled": enabled
                    }
                )
            except Exception as e:
                logging.exception(f"更新文档片段启用状态发生异常，错误信息：{str(e)}")
                if segment:
                    self.update(
                        segment,
                        error=str(e),
                        status=SegmentStatus.ERROR,
                        enabled=False,
                        disabled_at=datetime.now(),
                        stopped_at=datetime.now()
                    )
                raise FailException("更新文档片段启用状态失败，请稍后尝试")
        return segment

    def delete_segment(self
                       , dataset_id: UUID, document_id: UUID, segment_id: UUID, account: Account) -> Segment:
        """删除文档片段"""
        account_id = str(account.id)
        # 1. 校验文档片段的权限
        segment: Segment = self.get(Segment, segment_id)
        if (
                segment is None
                or str(segment.account_id) != account_id
                or segment.dataset_id != dataset_id
                or segment.document_id != document_id
        ):
            raise NotFoundException("该文档片段不存在，或无权限修改")
        # 2. 判断文档片段是否处于可用状态
        if segment.status not in [SegmentStatus.COMPLETED, SegmentStatus.ERROR]:
            raise FailException("当前片段处于不可删除状态，请稍后重试")
        # 3. 删除文档片段并获取该片段的文档信息
        document = segment.document
        self.delete(segment)

        # 4. 同步删除关键表中属于该片段 的关键词
        self.keyword_table_service.delete_keyword_table_from_ids(dataset_id, [segment_id])
        # 5. 同步删除微量数据库存储的记录
        try:
            self.vector_database_service.collection.data.delete_by_id(str(segment.node_id))
        except Exception as e:
            logging.exception(f"删除文档片段失败，segment_id:{segment_id}, error:{str(e)}")
        # 6. 更新文档信息，包含：字符总数，token总数
        document_character_count, document_token_count = self.db.session.query(
            func.coalesce(func.sum(Segment.character_count), 0),
            func.coalesce(func.sum(Segment.token_count), 0)
        ).first()
        self.update(
            document,
            character_count=document_character_count,
            token_count=document_token_count
        )
        return segment
