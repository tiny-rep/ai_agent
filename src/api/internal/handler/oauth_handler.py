from dataclasses import dataclass

from injector import inject

from internal.schema.oauth_schema import AuthorizeReq, AuthorizeResp
from internal.service.oauth_service import OAuthService
from pkg.reponse import success_json, validate_error_json


@inject
@dataclass
class OAuthHandler:
    """第三方授权认证接口"""
    oauth_service: OAuthService

    def provider(self, provider_name: str) -> str:
        """根据provider_name获取授权认证重定向地址"""
        oauth = self.oauth_service.get_oauth_by_provider_name(provider_name)

        redirect_url = oauth.get_authorization_url()

        return success_json({"redirect_url": redirect_url})

    def authorize(self, provider_name: str):
        """根据provider_name + code获取第三方授权信息"""
        req = AuthorizeReq()
        if not req.validate():
            return validate_error_json(req.errors)

        credential = self.oauth_service.oatuh_login(provider_name, req.code.data)

        return success_json(AuthorizeResp().dump(credential))
