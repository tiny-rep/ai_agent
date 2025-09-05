import mimetypes
import os
from dataclasses import dataclass
from typing import Any

from flask import current_app
from injector import inject
from pydantic import BaseModel

from internal.core.tools.builtin_tools.categories import BuiltinCategoryManager
from internal.core.tools.builtin_tools.entities import Provider
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.exception import NotFoundException


@inject
@dataclass
class BuiltinToolService:
    """内置工具服务"""
    builtin_provider_manager: BuiltinProviderManager
    builtin_category_manager: BuiltinCategoryManager

    def get_builtin_tools(self):
        """获取所有内置工具"""
        # 1. 所有所有工具提供商
        providers = self.builtin_provider_manager.get_providers()

        # 2. 遍历提供商获取所有工具实体
        builtin_tools = []
        for provider in providers:
            provider_entity = provider.provider_entity
            builtin_tool = {
                **provider_entity.model_dump(exclude=["icon"]),
                "tools": []
            }
            # 3. 工具实体
            tool_entities = provider.get_tool_entities()
            for tool_entity in tool_entities:
                # 4. 提取工具函数
                tool = provider.get_tool(tool_entity.name)

                # 5. 构建工具返回实体
                tool_dict = {
                    **tool_entity.model_dump(),
                    "inputs": self.get_tool_inputs(tool)
                }
                builtin_tool["tools"].append(tool_dict)
            builtin_tools.append(builtin_tool)
        return builtin_tools

    def get_provider_tool(self, provider_name: str, tool_name: str):
        """根据传送的提供者名字、工具名字，获取工具详细信息"""
        # 1. 获取内置的提供商
        provier: Provider = self.builtin_provider_manager.get_provider(provider_name)
        if provier is None:
            raise NotFoundException(f"该提供商{provider_name}不存在")

        # 2. 获取提供商下对应的工具
        tool_entity = provier.get_tool_entity(tool_name)
        if tool_entity is None:
            raise NotFoundException(f"该工具{tool_name}不存在")

        # 3. 组件提供商和工具实体
        provider_entity = provier.provider_entity
        tool = provier.get_tool(tool_name)
        builtin_tool = {
            "provider": {**provider_entity.model_dump(exclude=["icon", "created_at"])},
            **tool_entity.model_dump(),
            "create_id": provider_entity.created_at,
            "inputs": self.get_tool_inputs(tool)
        }
        return builtin_tool

    def get_provider_icon(self, provider_name: str) -> tuple[bytes, str]:
        """获取提供者Icon流信息"""
        # 1. 获取内置的提供商
        provier: Provider = self.builtin_provider_manager.get_provider(provider_name)
        if provier is None:
            raise NotFoundException(f"该提供商{provider_name}不存在")

        # 2. 获取项目的根路径信息
        root_path = os.path.dirname(os.path.dirname(current_app.root_path))

        # 3. 拼接路径
        provider_path = os.path.join(
            root_path,
            "internal", "core", "tools", "builtin_tools", "providers", provider_name
        )

        # 4. 拼接得到icon对应的路径
        icon_path = os.path.join(provider_path, "_assert", provier.provider_entity.icon)

        # 5. 检测Icon是否存在
        if not os.path.exists(icon_path):
            raise NotFoundException(f"该工具提供者_assert下未提供图标--34 {icon_path}")

        # 6. 读取Icon类型
        minetype, _ = mimetypes.guess_type(icon_path)
        minetype = minetype or "application/octet-stream"

        # 7. 读取icon字节数据
        with open(icon_path, "rb") as f:
            byte_data = f.read()
            return byte_data, minetype

    def get_provider_tool_fun(self, provider_name: str, tool_name: str):
        """根据传送的提供者名字、工具名字，获取工具详细信息"""
        # 1. 获取内置的提供商
        provier: Provider = self.builtin_provider_manager.get_provider(provider_name)
        if provier is None:
            raise NotFoundException(f"该提供商{provider_name}不存在")

        # 2. 获取提供商下对应的工具
        tool_entity = provier.get_tool_entity(tool_name)
        if tool_entity is None:
            raise NotFoundException(f"该工具{tool_name}不存在")

        # 3. 组件提供商和工具实体
        tool = provier.get_tool(tool_name)
        return tool

    def get_categories(self) -> list[dict[str, Any]]:
        category_map = self.builtin_category_manager.get_category_map()
        ls = []
        for category in category_map.values():
            ls.append({
                "name": category["entity"].name,
                "category": category["entity"].category,
                "icon": category["icon"]
            })
        return ls

    @classmethod
    def get_tool_inputs(cls, tool) -> list:
        """根据工具函数，获取工具输入参数"""
        inputs = []
        if hasattr(tool, "args_schema") and issubclass(tool.args_schema, BaseModel):
            for field_name, model_field in tool.args_schema.__fields__.items():
                inputs.append({
                    "name": field_name,
                    "description": model_field.description or "",
                    "required": model_field.is_required(),
                    "type": model_field.annotation.__name__
                })
        return inputs
