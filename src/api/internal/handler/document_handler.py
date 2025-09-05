from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.document_schema import (
    CreateDocumentsReq,
    CreateDocumentsResp, GetDocumentResp, GetDocumentsWithPageReq, GetDocumentsWithPageResp, UpdateDocumentNameReq,
    UpdateDocumentEnabledReq
)
from internal.service import DocumentService
from pkg.paginator import PageModel
from pkg.reponse import validate_error_json, success_json, success_message


@inject
@dataclass
class DocumentHandler:
    """文档处理器"""

    document_service: DocumentService

    @login_required
    def create_document(self, dataset_id: UUID):
        """知识库新增加/上传文档列表"""
        req = CreateDocumentsReq()
        if not req.validate():
            return validate_error_json(req.errors)

        documents, batch = self.document_service.create_document(dataset_id, current_user, **req.data)

        resp = CreateDocumentsResp()
        return success_json(resp.dump((documents, batch)))

    @login_required
    def get_document(self, dataset_id: UUID, document_id: UUID):
        """获取文档详细信息"""
        document = self.document_service.get_document(dataset_id, document_id, current_user)

        resp = GetDocumentResp()

        return success_json(resp.dump(document))

    @login_required
    def update_document_name(self, dataset_id: UUID, document_id: UUID):
        """更新文件名称信息"""
        req = UpdateDocumentNameReq()
        if not req.validate():
            validate_error_json(req.errors)

        self.document_service.update_document(dataset_id, document_id, current_user, name=req.name.data)
        return success_message("更新文档名称成功")

    @login_required
    def update_document_enabled(self, dataset_id: UUID, document_id: UUID):
        """更新文档启用状态"""
        req = UpdateDocumentEnabledReq()
        if not req.validate():
            validate_error_json(req.errors)

        self.document_service.update_document_enabled(dataset_id, document_id, req.enabled.data, current_user)

        return success_message("更新文档启用状态成功")

    @login_required
    def delete_document(self, dataset_id: UUID, document_id: UUID):
        """删除文档"""
        self.document_service.delete_document(dataset_id, document_id, current_user)

        return success_message("删除文档成功")

    @login_required
    def get_documents_status(self, dataset_id: UUID, batch: str):
        """根据知识库Id+批次Id，获取文档的状态"""
        documents_status = self.document_service.get_document_status(dataset_id, batch, current_user)
        return success_json(documents_status)

    @login_required
    def get_documents_with_page(self, dataset_id: UUID):
        """根据知识库Id，获取对应知识库下的所有文档"""
        # 1. 验证参数
        req = GetDocumentsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        # 2. 调用分页
        documents, paginator = self.document_service.get_documents_with_page(dataset_id, req, current_user)

        resp = GetDocumentsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(documents), paginator=paginator))
