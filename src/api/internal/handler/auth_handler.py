from dataclasses import dataclass

from flask_login import login_required, logout_user
from injector import inject

from internal.schema.auth_schema import PasswordLoginReq, PasswordLoginResp
from internal.service import AccountService
from pkg.reponse import validate_error_json, success_json, success_message


@inject
@dataclass
class AuthHandler:
    """第三方授权认证模块处理器"""
    account_service: AccountService

    def password_login(self):
        """账号+密码登录"""
        req = PasswordLoginReq()
        if not req.validate():
            return validate_error_json(req.errors)

        credential = self.account_service.password_login(req.email.data, req.password.data)

        resp = PasswordLoginResp()
        return success_json(resp.dump(credential))

    @login_required
    def logout(self):
        """退出登录"""
        logout_user()
        return success_message("退出登录成功")
