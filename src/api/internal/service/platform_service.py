from dataclasses import dataclass
from uuid import UUID

from injector import inject

from internal.model import Account, WechatConfig
from pkg.sqlalchemy import SQLAlchemy
from .app_service import AppService
from .base_service import BaseService
from ..entity.app_entity import AppStatus
from ..entity.platform_entity import WechatConfigStatus
from ..schema.platform_schema import UpdateWechatConfigReq


@inject
@dataclass
class PlatformService(BaseService):
    """第三方平台服务"""

    db: SQLAlchemy
    app_service: AppService

    def get_wechat_config(self, app_id: UUID, account: Account) -> WechatConfig:
        app = self.app_service.get_app(app_id, account)

        return app.wechat_config

    def update_wechat_config(self, app_id: UUID, req: UpdateWechatConfigReq, account: Account) -> WechatConfig:
        """weChat的配置"""
        app = self.app_service.get_app(app_id, account)

        status = WechatConfigStatus.UNCONFIGURED
        if req.wechat_app_id.data and req.wechat_app_secret.data and req.wechat_token.data:
            status = WechatConfigStatus.CONFIGURED

        if app.status == AppStatus.DRAFT and status == WechatConfigStatus.CONFIGURED:
            status = WechatConfigStatus.UNCONFIGURED

        wechat_config = app.wechat_config
        self.update(wechat_config, **{
            "wechat_app_id": req.wechat_app_id.data,
            "wechat_app_secret": req.wechat_app_secret.data,
            "wechat_token": req.wechat_token.data,
            "status": status
        })
        return wechat_config
