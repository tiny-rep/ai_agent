from dataclasses import dataclass
from typing import Optional

from flask import Request
from injector import inject

from internal.exception import UnauthorizedException
from internal.model import Account
from internal.service import JwtService, AccountService, ApiKeyService


@inject
@dataclass
class Middleware:
    """应用中间件，可以重写request_loader、unauthorized_handler"""
    jwt_service: JwtService
    account_service: AccountService
    api_key_service: ApiKeyService
    # 外链白名单
    ex_link_white_url = ["/web-apps/<string:ex_link_token>/conversations/<uuid:end_user_id>/ex-link",
                         "/web-apps/<string:ex_link_token>/ex-link/chat",
                         "/web-apps/<string:ex_link_token>/ex-link",
                         "/conversations/<uuid:conversation_id>/messages/ex-link/<uuid:end_user_id>",
                         "/conversations/<uuid:conversation_id>/delete/ex-link/<uuid:end_user_id>",
                         "/conversations/<uuid:conversation_id>/messages/<uuid:message_id>/delete/ex-link/<uuid:end_user_id>",
                         "/conversations/<uuid:conversation_id>/name/ex-link/<uuid:end_user_id>",
                         "/conversations/<uuid:conversation_id>/name/ex-link/<uuid:end_user_id>",
                         "/conversations/<uuid:conversation_id>/is-pinned/ex-link/<uuid:end_user_id>",
                         "/ai/<uuid:end_user_id>/suggested-questions/ex-link",
                         "/web-apps/<string:ex_link_token>/ex-link/chat/<uuid:task_id>/stop",
                         "/openapi/<uuid:end_user_id>/app/<uuid:app_id>/init-conversation/<uuid:conversation_id>"]

    def request_loader(self, request: Request) -> Optional[Account]:
        """登录管理器的请求加载器"""
        if request.blueprint == "llmops":
            access_token = self._validate_credential(request)
            payload = self.jwt_service.paser_token(access_token)
            # add 2025-04-14 sam 增加限制ex-link链接访问其后台管理系统的能力
            iss_value = payload.get("iss")
            if iss_value == 'llmops-exLink':
                # 外链接模式
                url_rule = request.url_rule.rule
                if not url_rule in self.ex_link_white_url:
                    raise UnauthorizedException("当前账号访问不合法，请重新登录")

            account_id = payload.get("sub")
            account = self.account_service.get_account(account_id)
            if not account:
                raise UnauthorizedException("当前账号不存在，请重新登录")
            return account
        elif request.blueprint == "openapi":
            api_key = self._validate_credential(request)
            api_key_record = self.api_key_service.get_api_key_by_credential(api_key)

            if not api_key_record or not api_key_record.is_active:
                raise UnauthorizedException("该秘钥不存或未激活")

            account_record = api_key_record.account
            return account_record
        else:
            return None

    @classmethod
    def _validate_credential(cls, request: Request) -> str:
        """校验请求头中的凭证信息，包含：access_token、api_key"""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise UnauthorizedException("该接口需要登录后才能访问，请登录后尝试")

        # token格式：Authorization: Bearer access_token
        if " " not in auth_header:
            raise UnauthorizedException("该接口需要授权才能访问，验证格式失败")

        auth_schema, credential = auth_header.split(None, 1)
        if auth_schema.lower() != "bearer":
            raise UnauthorizedException("该接口需要授权才能访问，验证格式失败")

        return credential
