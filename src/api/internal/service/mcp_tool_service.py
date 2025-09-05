from dataclasses import dataclass
from uuid import UUID

from injector import inject
from sqlalchemy import desc

from internal.model import Account, McpTool
from internal.schema.mcp_schema import CreateMcpToolRequest, GetMcpToolsWithPageReq, UpdateMcpToolRequest
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from ..exception import ValidateErrorException, NotFoundException


@inject
@dataclass
class McpToolService(BaseService):
    """Mcp Server 服务对象"""
    db: SQLAlchemy

    def create_mcp_tool(self, req: CreateMcpToolRequest, account: Account):
        """创建Mcp工具"""
        account_id = str(account.id)
        mcp_tool_entity = self.db.session.query(McpTool).filter_by(
            account_id=account_id,
            name=req.name.data
        ).one_or_none()
        if mcp_tool_entity:
            raise ValidateErrorException(f"名为{req.name.data}的Mcp工具已存")
        self.create(
            McpTool,
            account_id=account_id,
            name=req.name.data,
            icon=req.icon.data,
            description=req.description.data,
            transport_type=req.transport_type.data,
            parameters=req.mcp_params.data,
            provider_name=req.provider_name.data
        )

    def update_mcp_tool(self, mcp_tool_id: UUID, req: UpdateMcpToolRequest, account: Account):
        """创建Mcp工具"""
        account_id = str(account.id)
        mcp_tool_entity = self.db.session.query(McpTool).filter_by(
            account_id=account_id,
            id=mcp_tool_id
        ).one_or_none()
        if not mcp_tool_entity:
            raise ValidateErrorException(f"名为[{req.name.data}]的Mcp工具不存在或者不属于当前用户")

        # 检查当前账号下是否存在同名Mcp Tool
        check_mcp_tool_entity = self.db.session.query(McpTool).filter(
            McpTool.account_id == account_id,
            McpTool.name == req.name.data,
            McpTool.id != mcp_tool_id
        ).one_or_none()
        if check_mcp_tool_entity:
            raise ValidateErrorException(f"名为[{req.name.data}]的Mcp工具已存在，请更新名称")

        self.update(
            mcp_tool_entity,
            name=req.name.data,
            icon=req.icon.data,
            description=req.description.data,
            transport_type=req.transport_type.data,
            parameters=req.mcp_params.data,
            provider_name=req.provider_name.data
        )

    def get_mcp_tool(self, mcp_tool_id: UUID, account: Account) -> McpTool:
        """获取mcpTool详细参数信息"""
        account_id = str(account.id)

        mcp_tool = self.get(McpTool, mcp_tool_id)

        if mcp_tool is None or str(mcp_tool.account_id) != account_id:
            raise NotFoundException("该Mcp工具不存在")
        return mcp_tool

    def delete_mcp_tool(self, mcp_tool_id: UUID, account: Account) -> None:
        """根据mcp_tool_id删除工具"""

        # 1. 根据传递的provider_id查询API工具提供者信息并校验
        mcp_tool = self.get_mcp_tool(mcp_tool_id, account)

        self.delete(mcp_tool)

    def get_mcp_tools_with_page(self, req: GetMcpToolsWithPageReq, account: Account):
        """mcp tool 列表查询"""
        account_id = str(account.id)

        paginator = Paginator(db=self.db, req=req)

        # 2. 过滤
        filters = [McpTool.account_id == account_id]
        if req.search_word.data:
            filters.append(McpTool.name.ilike(f"%{req.search_word.data}%"))

        # 3 执行查询
        mcp_tools = paginator.paginate(
            self.db.session.query(McpTool).filter(*filters).order_by(desc("created_at"))
        )

        return mcp_tools, paginator
