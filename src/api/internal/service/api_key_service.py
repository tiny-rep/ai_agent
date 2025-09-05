import secrets
from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from pkg.paginator import PaginatorReq, Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from ..exception import ForbiddenException
from ..model import Account, ApiKey
from ..schema.api_key_schema import CreateApiKeyReq


@inject
@dataclass
class ApiKeyService(BaseService):
    """Api秘钥服务"""

    db: SQLAlchemy

    def create_api_key(self, req: CreateApiKeyReq, account: Account):
        """创建Api_key秘钥"""
        return self.create(
            ApiKey,
            account_id=account.id,
            api_key=self.generate_api_key(),
            is_active=req.is_active.data,
            remark=req.remark.data
        )

    def get_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """获取ApiKey秘钥详细信息"""
        api_key = self.get(ApiKey, api_key_id)
        if not api_key or api_key.account_id != account.id:
            raise ForbiddenException("API秘钥不存在或无权限")
        return api_key

    def get_api_key_by_credential(self, api_key: str) -> ApiKey:
        return self.db.session.query(ApiKey).filter(
            ApiKey.api_key == api_key
        ).one_or_none()

    def update_api_key(self, api_key_id: UUID, account: Account, **kwargs) -> ApiKey:
        """修改api_key"""
        api_key = self.get_api_key(api_key_id, account)
        self.update(api_key, **kwargs)
        return api_key

    def delete_api_key(self, api_key_id: UUID, account: Account) -> ApiKey:
        """删除APIKey"""
        api_key = self.get_api_key(api_key_id, account)
        self.delete(api_key)
        return api_key

    def get_api_keys_with_page(self, req: PaginatorReq, account: Account) -> tuple[list[ApiKey], Paginator]:
        """获取Api秘钥分页信息"""
        paginator = Paginator(db=self.db, req=req)
        api_keys = paginator.paginate(
            self.db.session.query(ApiKey).filter(
                ApiKey.account_id == account.id
            ).order_by(desc("created_at"))
        )
        return api_keys, paginator

    @classmethod
    def generate_api_key(cls, api_key_prefix: str = "llmops-v1/") -> str:
        return api_key_prefix + secrets.token_urlsafe(48)
