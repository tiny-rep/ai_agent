import logging
import random
import time
from dataclasses import dataclass
from uuid import UUID

from future.backports.datetime import datetime
from injector import inject
from redis import Redis
from sqlalchemy import desc, asc, func

from internal.task.document_task import build_documents, update_document_enabled, delete_document
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from ..entity.cache_entity import LOCK_DOCUMENT_UPDATE_ENABLED, LOCK_EXPIRE_TIME
from ..entity.dataset_entity import ProcessType, SegmentStatus, DocumentStatus
from ..entity.upload_file_entity import ALLOWED_DOCUMENT_EXTENSION
from ..exception import ForbiddenException, FailException, NotFoundException
from ..lib.helper import datetime_to_timestamp
from ..model import Dataset, UploadFile, ProcessRule, Document, Segment, Account
from ..schema.document_schema import GetDocumentsWithPageReq


@inject
@dataclass
class DocumentService(BaseService):
    """文档服务"""
    db: SQLAlchemy
    redis_client: Redis

    def create_document(self,
                        dataset_id: UUID,
                        account: Account,
                        upload_file_ids: list[UUID],
                        process_type: str = ProcessType.AUTOMATIC,
                        rule: dict = True):
        """创建文档列表，并调用异步任务"""
        account_id = str(account.id)

        # 1. 检测知识库权限
        dataset: Dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            raise ForbiddenException("当前用户无该知识库权限或知识库不存在")

        # 2. 提取文件并校验文件权限与扩展名
        upload_files = self.db.session.query(UploadFile).filter(
            UploadFile.account_id == account_id,
            UploadFile.id.in_(upload_file_ids)
        ).all()

        upload_files = [
            upload_file for upload_file in upload_files
            if upload_file.extension.lower() in ALLOWED_DOCUMENT_EXTENSION
        ]

        if len(upload_files) == 0:
            logging.warning(
                f"上传文档列表未解析到合法文件，account_id:{account_id}, dataset_id:{dataset_id}, upload_file_ids:{upload_file_ids}"
            )
            raise FailException("暂未解析到合法文件，请重新上传")
        # 3. 创建批次与处理规则并记录到数据库中
        batch = time.strftime("%Y%m%d%H%M%S") + str(random.randint(100000, 999999))
        process_rule: ProcessRule = self.create(
            ProcessRule,
            account_id=account_id,
            dataset_id=dataset_id,
            mode=process_type,
            rule=rule
        )

        # 4. 获取当前知识库的最新文档位置
        position = self.get_latest_document_position(dataset_id)

        # 5. 循环遍历所有合法的上传文件列表并记录
        documents = []
        for upload_file in upload_files:
            position += 1
            document = self.create(
                Document,
                account_id=account_id,
                dataset_id=dataset_id,
                upload_file_id=upload_file.id,
                process_rule_id=process_rule.id,
                batch=batch,
                name=upload_file.name,
                position=position
            )
            documents.append(document)

        # 6. 调用异步任务
        build_documents.delay([document.id for document in documents])

        # 7. 返回文档列表与处理批次
        return documents, batch

    def get_document_status(self, dataset_id: UUID, batch: str, account: Account) -> list[dict]:
        """查询知识库Id+批次 文档列表的状态"""
        account_id = str(account.id)

        # 1. 检测知识库权限
        dataset: Dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            raise ForbiddenException("当前用户无该知识库权限或知识库不存在")

        # 2. 查询当前知识库下该批次的文档列表
        documents = self.db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
            Document.batch == batch
        ).order_by(asc("position")).all()
        if documents is None or len(documents) == 0:
            raise NotFoundException("该批次未发现文档，请核实后重试")

        # 3. 循环遍历文档列表提取文档的状态信息
        documents_status = []
        for document in documents:
            # 4. 查询每个文档总片段数与构建完成的片段数
            segment_count = self.db.session.query(func.count(Segment.id)).filter(
                Segment.document_id == document.id
            ).scalar()
            completed_segment_count = self.db.session.query(func.count(Segment.id)).filter(
                Segment.document_id == document.id,
                Segment.status == SegmentStatus.COMPLETED
            ).scalar()
            upload_file: UploadFile = document.upload_file
            documents_status.append({
                "id": document.id,
                "name": document.name,
                "size": upload_file.size,
                "extension": upload_file.extension,
                "mime_type": upload_file.mime_type,
                "position": document.position,
                "segment_count": segment_count,
                "completed_segment_count": completed_segment_count,
                "error": document.error,
                "status": document.status,
                "processing_started_at": datetime_to_timestamp(document.processing_started_at),
                "parsing_completed_at": datetime_to_timestamp(document.parsing_completed_at),
                "splitting_completed_at": datetime_to_timestamp(document.splitting_completed_at),
                "indexing_completed_at": datetime_to_timestamp(document.indexing_completed_at),
                "completed_at": datetime_to_timestamp(document.completed_at),
                "stopped_at": datetime_to_timestamp(document.stopped_at),
                "created_at": datetime_to_timestamp(document.created_at),
            })
        return documents_status

    def get_document(self, dataset_id: UUID, document_id: UUID, account: Account) -> Document:
        """知识库id+文档id获取文档记录信息"""
        account_id = str(account.id)

        document: Document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or str(document.account_id) != account_id:
            raise ForbiddenException("无权查看")

        return document

    def update_document(self, dataset_id: UUID, document_id: UUID, account: Account, **kwargs) -> Document:
        """根据知识库Id+文档Id，修改文档信息"""
        account_id = str(account.id)

        document: Document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or str(document.account_id) != account_id:
            raise ForbiddenException("无权查看")

        return self.update(
            document,
            **kwargs
        )

    def update_document_enabled(self, dataset_id: UUID, document_id: UUID, enabled: bool, account: Account) -> Document:
        """根据知识库Id+文档Id，更新文档的启用状态，同时异步更新weaviate向量数据库中的数据"""
        account_id = str(account.id)

        document: Document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or str(document.account_id) != account_id:
            raise ForbiddenException("无权查看")

        # 2. 查看状态是否可用
        if document.status != DocumentStatus.COMPLETED:
            raise ForbiddenException("当前文档处于不可修改状态，请稍后重试")

        # 3. 判断修改的启用状态是否正确，需与当前的状态相反
        if document.enabled == enabled:
            raise FailException(f"文档状态修改错误，当前已是{'启用' if enabled else '禁用'}状态")

        # 4. 获取更新文档启用状态的缓存键并检测是否上锁
        cache_key = LOCK_DOCUMENT_UPDATE_ENABLED.format(document_id=document_id)
        cache_result = self.redis_client.get(cache_key)
        if cache_result is not None:
            raise FailException("当前文档正在修改启用状态，请稍后")

        # 5.修改文档的启用状态并设置缓存键，缓存为600s
        self.update(
            document,
            enabled=enabled,
            disabled_at=None if enabled else datetime.now()
        )
        self.redis_client.setex(cache_key, LOCK_EXPIRE_TIME, 1)

        # 6.启用异步任务
        update_document_enabled.delay(document.id)

        return document

    def delete_document(self, dataset_id: UUID, document_id: UUID, account: Account) -> Document:
        """根据知识库Id+文档Id删除数据"""
        account_id = str(account.id)

        document: Document = self.get(Document, document_id)
        if document is None:
            raise NotFoundException("该文档不存在，请核实后重试")
        if document.dataset_id != dataset_id or str(document.account_id) != account_id:
            raise ForbiddenException("无权查看")

        # 2. 判断是否可删除，只用有构建完成/出错的 才可以删除，其他状态需要等构建完成
        if document.status not in [DocumentStatus.COMPLETED, DocumentStatus.ERROR]:
            raise FailException("当前文档处于不可删除状态，请稍后重试")

        # 3. 删除数据
        self.delete(document)

        # 4. 调用异步，包含：更新关键词表、片段数据表、向量记录删除
        delete_document.delay(dataset_id, document_id)

        return document

    def get_documents_with_page(self,
                                dataset_id: UUID,
                                req: GetDocumentsWithPageReq, account: Account) -> tuple[list[Document], Paginator]:
        """获取知识库Id+请求数据 获取文档分页数据"""
        account_id = str(account.id)

        # 1.获取知识库并校验权限
        dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            raise NotFoundException("该知识库不存在，或无权限")

        # 2. 构建分页器
        paginator = Paginator(db=self.db, req=req)

        # 3.构建筛选器
        filters = [
            Document.account_id == account_id,
            Document.dataset_id == dataset_id
        ]
        if req.search_word.data:
            filters.append(Document.name.ilike(f"%{req.search_word.data}%"))

        # 4. 分页并获取数据
        documents = paginator.paginate(
            self.db.session.query(Document).filter(*filters).order_by(desc("created_at"))
        )
        return documents, paginator

    def get_latest_document_position(self, dataset_id: UUID) -> int:
        """根据知识库id 获取最新文档位置"""
        document = self.db.session.query(Document).filter(
            Document.dataset_id == dataset_id
        ).order_by(desc("position")).first()
        return document.position if document else 0
