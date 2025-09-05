import io
from dataclasses import dataclass

from flask import send_file
from injector import inject

from internal.service import BuiltinToolService
from pkg.reponse import success_json, success_message


@inject
@dataclass
class BuiltinToolHandler:
    builtin_tool_service: BuiltinToolService

    def get_builtin_tools(self):
        """获取所有内置工具信息"""
        builtin_tools = self.builtin_tool_service.get_builtin_tools()
        return success_json(builtin_tools)

    def get_provider_tool(self, provider_name: str, tool_name: str):
        """根据服务提供者名称、工具名称获取工具信息"""
        builtin_tool = self.builtin_tool_service.get_provider_tool(provider_name, tool_name)
        return success_json(builtin_tool)

    def get_provider_icon(self, provider_name: str):
        """根据服务提供商获取Icon"""
        byte, minetype = self.builtin_tool_service.get_provider_icon(provider_name)
        return send_file(io.BytesIO(byte), minetype)

    def get_categories(self):
        """获取所有内置提供商的分类信息"""
        categories = self.builtin_tool_service.get_categories()
        return success_json(categories)

    def tool_exec_test(self, provider_name: str, tool_name: str):
        fun = self.builtin_tool_service.get_provider_tool_fun(provider_name, tool_name)
        val = fun().invoke("测试数据")
        return success_message(val)
