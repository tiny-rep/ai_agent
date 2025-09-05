from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import current_user, login_required
from injector import inject

from internal.schema.mcp_schema import GetMcpToolsWithPageReq, GetMcpToolsWithPageResp, CreateMcpToolRequest, \
    UpdateMcpToolRequest, GetMcpToolResp
from internal.service import McpToolService
from pkg.paginator import PageModel
from pkg.reponse import validate_error_json, success_json, success_message


@inject
@dataclass
class McpToolHandler:
    """Mcp sever处理器"""

    mcp_tool_service: McpToolService

    @login_required
    def get_mcp_tools_with_page(self):
        req = GetMcpToolsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        mcp_tools, paginator = self.mcp_tool_service.get_mcp_tools_with_page(req, current_user)
        resp = GetMcpToolsWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(mcp_tools), paginator=paginator))

    @login_required
    def create_mcp_tool(self):
        req = CreateMcpToolRequest()
        if not req.validate():
            return validate_error_json(req.errors)

        self.mcp_tool_service.create_mcp_tool(req, current_user)

        return success_message("mcp server创建成功")

    @login_required
    def update_mcp_tool(self, mcp_tool_id: UUID):
        req = UpdateMcpToolRequest()
        if not req.validate():
            return validate_error_json(req.errors)

        self.mcp_tool_service.update_mcp_tool(mcp_tool_id, req, current_user)

        return success_message("mcp server修改成功")

    @login_required
    def delete_mcp_tool(self, mcp_tool_id: UUID):
        self.mcp_tool_service.delete_mcp_tool(mcp_tool_id, current_user)
        return success_message("mcp server删除成功")

    @login_required
    def get_mcp_tool(self, mcp_tool_id: UUID):
        mcp_tool = self.mcp_tool_service.get_mcp_tool(mcp_tool_id, current_user)
        resp = GetMcpToolResp()
        return success_json(resp.dump(mcp_tool))
