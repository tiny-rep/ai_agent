from dataclasses import dataclass
from uuid import UUID

from flask_login import login_required, current_user
from injector import inject

from internal.schema.api_key_schema import CreateApiKeyReq, UpdateApiKeyReq, UpdateApiKeyIsActiveReq, \
    GetApiKeysWithPageResp
from internal.service import ApiKeyService
from pkg.paginator import PaginatorReq, PageModel
from pkg.reponse import validate_error_json, success_message, success_json


@inject
@dataclass
class ApiKeyHandler:
    """ApiKey秘钥处理器"""

    api_key_service: ApiKeyService

    @login_required
    def create_api_key(self):
        """创建ApiKey"""
        req = CreateApiKeyReq()
        if not req.validate():
            return validate_error_json(req.errors)
        self.api_key_service.create_api_key(req, current_user)

        return success_message("API秘钥创建成功")

    @login_required
    def delete_api_key(self, api_key_id: UUID):
        self.api_key_service.delete_api_key(api_key_id, current_user)
        return success_message("API秘钥删除成功")

    @login_required
    def update_api_key(self, api_key_id: UUID):
        req = UpdateApiKeyReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.api_key_service.update_api_key(api_key_id, current_user, **req.data)

        return success_message("更新API秘钥成功")

    @login_required
    def update_api_key_is_active(self, api_key_id: UUID):
        req = UpdateApiKeyIsActiveReq()
        if not req.validate():
            return validate_error_json(req.errors)
        self.api_key_service.update_api_key(api_key_id, current_user, **req.data)

        return success_message("更新API秘钥激活状态成功")

    @login_required
    def get_api_keys_with_page(self):
        req = PaginatorReq()
        if not req.validate():
            return validate_error_json(req.errors)

        api_keys, paginator = self.api_key_service.get_api_keys_with_page(req, current_user)
        resp = GetApiKeysWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(api_keys), paginator=paginator))
