import urllib.parse

import requests

from .oauth import OAuth, OAuthUserInfo


class GitHubOAuth(OAuth):
    """GitHub第三方授权认证"""
    _AUTHORIZE_URL = "https://github.com/login/oauth/authorize"  # 跳转授权接口
    _ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"  # 获取授权令牌接口
    _USER_INFO_URL = "https://api.github.com/user"  # 获取用户信息接口
    _EMAIL_INFO_URL = "https://api.github.com/user/emails"  # 获取用户邮箱接口

    def get_provider(self) -> str:
        return "github"

    def get_authorization_url(self) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": "user:email"
        }
        return f"{self._AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def get_access_token(self, code: str) -> str:
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        headers = {"Accept": "application/json"}

        resp = requests.post(self._ACCESS_TOKEN_URL, data=data, headers=headers)
        resp.raise_for_status()
        resp_json = resp.json()

        access_token = resp_json.get("access_token")
        if not access_token:
            raise ValueError(f"github OAuth授权失败：{resp_json}")

        return access_token

    def get_raw_user_info(self, token: str) -> dict:
        headers = {"Authorization": f"token {token}"}
        resp = requests.get(self._USER_INFO_URL, headers=headers)
        resp.raise_for_status()
        raw_info = resp.json()

        email_resp = requests.get(self._EMAIL_INFO_URL, headers=headers)
        email_resp.raise_for_status()
        email_json = email_resp.json()

        primary_email = next((email for email in email_json if email.get("primary", None)), None)

        return {**raw_info, "email": primary_email.get("email", None)}

    def _transform_user_info(self, raw_info: dict) -> OAuthUserInfo:
        email = raw_info.get("email")
        if not email:
            email = f"{raw_info.get('id')}+{raw_info.get('login')}@user.no-reply@github.com"
        return OAuthUserInfo(
            id=str(raw_info.get("id")),
            name=str(raw_info.get("name")),
            email=str(email)
        )
