from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class OAuthUserInfo:
    """OAuth用户基础信息"""
    id: str
    name: str
    email: str


@dataclass
class OAuth(ABC):
    """oauth授权认证类"""
    client_id: str  # 客户端Id
    client_secret: str  # 客户端秘钥
    redirect_uri: str  # 重定向uri

    @abstractmethod
    def get_provider(self) -> str:
        """获取提供者对应名称"""
        pass

    @abstractmethod
    def get_authorization_url(self) -> str:
        """获取跳转授权谁的URL地址"""
        pass

    @abstractmethod
    def get_access_token(self, code: str) -> str:
        """根据传入的Token代码获取授权令牌"""
        pass

    @abstractmethod
    def get_raw_user_info(self, token: str) -> dict:
        """根据传入的token获取OAuth原始信息"""
        pass

    def get_user_info(self, token: str) -> OAuthUserInfo:
        """根据token获取OAthUserInfo对象"""
        raw_info = self.get_raw_user_info(token)
        return self._transform_user_info(raw_info)

    @abstractmethod
    def _transform_user_info(self, raw_info: dict) -> OAuthUserInfo:
        """将OAuth原始信息转换为OAuthUserInfo"""
        pass
