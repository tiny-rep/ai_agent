from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject
from weaviate.classes.query import Filter

from internal.core.file_extractor import FileExtractor
from internal.schema.dataset_schema import CreateDatasetReq, GetDatasetResp, UpdateDatasetReq, GetDatasetsWithPageReq, \
    GetDatasetsWithPageResp, GetDatasetQueriesResp, HitReq
from internal.service import DatasetService, EmbeddingsService, JiebaService, VectorDatabaseService
from internal.service.upload_file_service import UploadFileService
from pkg.paginator import PageModel
from pkg.reponse import validate_error_json, success_json, success_message


@inject
@dataclass
class DatasetHandler:
    """知识库处理器"""
    dataset_service: DatasetService
    embeddings_service: EmbeddingsService
    jieba_service: JiebaService
    file_extractor: FileExtractor
    upload_file_service: UploadFileService
    vector_dataset_service: VectorDatabaseService

    def embeddings_query(self):
        query = request.args.get("query")

        # upload_file = self.upload_file_service.get(UploadFile, "df1d7740-a8c5-4534-b06f-5211493eb2b2")
        # docs = self.file_extractor.load(upload_file, True)
        # return success_json({"docs": docs})

        # cont = self.jieba_service.extract_keywords(query)
        # return success_json({"cont": cont})
        # vectors = self.embeddings_service.embeddings.embed_query(query)
        # return success_json({"vecotrs": vectors})

        search_result = self.vector_dataset_service.vector_store.similarity_search_with_relevance_scores(
            query="标题",
            k=4,
            **{
                "filters": Filter.all_of([
                    Filter.by_property("document_enabled").equal(False)
                ])
            }
        )
        docs = []
        for doc, score in search_result:
            docs.append(f"{doc.metadata['document_enabled']}:{doc.page_content}")
        return success_json({"vectors": docs})

    @login_required
    def hit(self, dataset_id: UUID):
        """召回测试接口"""
        req = HitReq()
        if not req.validate():
            return validate_error_json(req.errors)

        hit_result = self.dataset_service.hit(dataset_id, req, current_user)

        return success_json(hit_result)

    @login_required
    def create_dataset(self):
        """创建知识库"""
        req = CreateDatasetReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.dataset_service.create_dataset(req, current_user)

        return success_message("创建知识库成功")

    @login_required
    def update_dataset(self, dataset_id: UUID):
        """修改知识库"""
        req = UpdateDatasetReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.dataset_service.update_dataset(dataset_id, req, current_user)

        return success_message("更新知识库成功")

    @login_required
    def get_dataset(self, dataset_id: UUID):
        """获取知识库详情"""
        dataset = self.dataset_service.get_dataset(dataset_id, current_user)
        resp = GetDatasetResp()
        return success_json(resp.dump(dataset))

    @login_required
    def get_dataset_queries(self, dataset_id: UUID):
        """获取知识库最近查询的10条记录"""
        dataset_queries = self.dataset_service.get_dataset_queries(dataset_id, current_user)
        resp = GetDatasetQueriesResp(many=True)
        return success_json(resp.dump(dataset_queries))

    @login_required
    def delete_dataset(self, dataset_id: UUID):
        """删除知识库"""
        self.dataset_service.delete_dataset(dataset_id, current_user)
        return success_message("删除知识库成功")

    @login_required
    def get_datasets_with_page(self):
        """分页查询知识库列表"""
        req = GetDatasetsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        datasets, paginator = self.dataset_service.get_dataset_with_page(req, current_user)

        resp = GetDatasetsWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(datasets), paginator=paginator))
