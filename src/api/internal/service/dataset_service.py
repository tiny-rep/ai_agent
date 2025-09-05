from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from internal.entity.dataset_entity import DEFAULT_DATASET_DESCRIPTION_FORMATTER
from internal.exception import ValidateErrorException, NotFoundException, FailException
from internal.lib.helper import datetime_to_timestamp
from internal.model import Dataset, AppDatasetJoin, DatasetQuery, Segment, UploadFile, Account
from internal.schema.dataset_schema import CreateDatasetReq, UpdateDatasetReq, GetDatasetsWithPageReq, HitReq
from internal.service.base_service import BaseService
from internal.service.retrieval_service import RetrievalService
from internal.task.dataset_task import delete_dataset
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy


@inject
@dataclass
class DatasetService(BaseService):
    """知识库服务"""
    db: SQLAlchemy
    retrieval_service: RetrievalService

    def create_dataset(self, req: CreateDatasetReq, account: Account) -> Dataset:
        """创建dataset"""
        account_id = str(account.id)

        # 1. 检测是否存在同名知识库
        dataset = self.db.session.query(Dataset).filter_by(
            account_id=account_id,
            name=req.name.data
        ).one_or_none()
        if dataset:
            raise ValidateErrorException(f"该知识库{req.name.data}已存在")

        # 2. 检测是否传递了描述，如果没有传递补充上默认描述
        if req.description.data is None or req.description.data.strip() == "":
            req.description.data = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(name=req.name.data)

        # 3. 创建知识库并返回记录
        return self.create(
            Dataset,
            account_id=account_id,
            name=req.name.data,
            description=req.description.data,
            icon=req.icon.data
        )

    def get_dataset(self, dataset_id: UUID, account: Account) -> Dataset:
        """获取知识库详细信息"""
        account_id = str(account.id)

        dataset: Dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            raise NotFoundException("该知识库不存在")

        return dataset

    def get_dataset_queries(self, dataset_id: UUID, account: Account) -> list[DatasetQuery]:
        """查询知识库最近10条查询记录"""
        account_id = str(account.id)

        # 1.获取知识库并校验权限
        dataset: Dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            raise NotFoundException("该知识库不存在")
        # 2. 调用知识库查询模型查找最近10条记录
        dataset_queries = self.db.session.query(DatasetQuery).filter(
            DatasetQuery.dataset_id == dataset_id
        ).order_by(desc("created_at")).limit(10).all()

        return dataset_queries

    def update_dataset(self, dataset_id: UUID, req: UpdateDatasetReq, account: Account) -> Dataset:
        """修改知识库"""
        account_id = str(account.id)

        # 1. 检测知识库是否存在
        dataset: Dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            raise NotFoundException("该知识库不存在")

        # 2. 检测修改后的知识库名是否重名
        check_dataset = self.db.session.query(Dataset).filter(
            Dataset.account_id == account_id,
            Dataset.name == req.name.data,
            Dataset.id != dataset.id
        ).one_or_none()
        if check_dataset:
            raise ValidateErrorException(f"该知识库名称{req.name.data}已存在")

        # 3. 校验描述是否为空，为空要补充默认描述
        if req.description.data is None or req.description.data.strip() == "":
            req.description.data = DEFAULT_DATASET_DESCRIPTION_FORMATTER.format(name=req.name.data)

        # 4. 更新数据
        self.update(
            dataset,
            name=req.name.data,
            icon=req.icon.data,
            description=req.description.data
        )

        return dataset

    def delete_dataset(self, dataset_id: UUID, account: Account):
        """删除知识库"""
        account_id = str(account.id)

        # 1. 获取知识库并校验权限
        dataset: Dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            raise NotFoundException("该知识库不存在")

        try:
            # 2. 删除知识库基础记录及知识库和应用的关联记录
            self.delete(dataset)
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(
                    AppDatasetJoin.dataset_id == dataset_id
                ).delete()
            # 3. 调用异步任务执行后续操作
            delete_dataset.delay(dataset_id)
        except Exception as e:
            raise FailException("删除知识库失败")

    def get_dataset_with_page(self, req: GetDatasetsWithPageReq, account: Account) -> tuple[list[Dataset], Paginator]:
        """获取知识库分页+搜索列数据"""
        account_id = str(account.id)

        paginator = Paginator(db=self.db, req=req)

        filters = [Dataset.account_id == account_id]
        if req.search_word.data:
            filters.append(Dataset.name.like(f"%{req.search_word.data}%"))

        datasets = paginator.paginate(
            self.db.session.query(Dataset).filter(*filters).order_by(desc("created_at"))
        )

        return datasets, paginator

    def hit(self, dataset_id: UUID, req: HitReq, account: Account) -> list[dict]:
        """知识库 召回测试"""
        account_id = str(account.id)

        # 1. 检测知识库是否存在并校验
        dataset: Dataset = self.get(Dataset, dataset_id)
        if dataset is None or str(dataset.account_id) != account_id:
            raise NotFoundException("该知识库不存在")
        # 2. 调用检索服务执行检索
        lc_documents = self.retrieval_service.search_in_dataset(
            dataset_ids=[dataset_id],
            account_id=account.id,
            **req.data
        )
        lc_document_dict = {str(lc_document.metadata["segment_id"]): lc_document for lc_document in lc_documents}

        # 3. 根据检索到的数据查询对应的片段信息
        segments = self.db.session.query(Segment).filter(
            Segment.id.in_([str(lc_document.metadata["segment_id"]) for lc_document in lc_documents])
        )
        segment_dict = {str(segment.id): segment for segment in segments}

        # 4. 排序片段数据
        sorted_segments = [
            segment_dict[str(lc_document.metadata["segment_id"])]
            for lc_document in lc_documents
            if str(lc_document.metadata["segment_id"]) in segment_dict
        ]

        # 5. 组装响应格式
        hit_result = []
        for segment in sorted_segments:
            document = segment.document
            upload_file: UploadFile = document.upload_file
            hit_result.append({
                "id": segment.id,
                "document": {
                    "id": document.id,
                    "name": document.name,
                    "extension": upload_file.extension,
                    "mime_type": upload_file.mime_type
                },
                "dataset_id": segment.dataset_id,
                "score": lc_document_dict[str(segment.id)].metadata["score"],
                "position": segment.position,
                "content": segment.content,
                "keywords": segment.keywords,
                "character_count": segment.character_count,
                "token_count": segment.token_count,
                "hit_count": segment.hit_count,
                "enabled": segment.enabled,
                "disabled_at": datetime_to_timestamp(segment.disabled_at),
                "status": segment.status,
                "error": segment.error,
                "updated_at": datetime_to_timestamp(segment.updated_at),
                "created_at": datetime_to_timestamp(segment.created_at)
            })
        return hit_result
