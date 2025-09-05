import os.path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from internal.lib.helper import dynamic_import
from .tool_entity import ToolEntity


class ProviderEntity(BaseModel):
    """服务提供商实体，映射的数据是providers.yaml里的每条记录"""
    name: str  # 名字
    label: str  # 标签、用于前端显示
    description: str  # 描述
    icon: str  # 图标地址
    background: str  # 图标背景色
    category: str  # 分类信息
    created_at: int = 0  # 提供商/工具的创建时间戳


class Provider(BaseModel):
    """服务提供高实体，提供所有工具、描述、图标等多个信息"""
    name: str  # 服务提供商名称
    position: int  # 服务提供商顺序
    provider_entity: ProviderEntity  # 服务提供商实体
    tool_entity_map: dict[str, ToolEntity] = Field(default_factory=dict)  # 工具实体类映射表
    tool_func_map: dict[str, Any] = Field(default_factory=dict)  # 工具函数映射表

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._provider_init()

    def get_tool(self, tool_name: str) -> Any:
        """根据工具名字，来获取到该服务提供商下的指定工具"""
        return self.tool_func_map.get(tool_name)

    def get_tool_entity(self, tool_name: str) -> ToolEntity:
        """根据工具的名字，来获取到该服务提供商下的指定工具和实体/信息"""
        return self.tool_entity_map.get(tool_name)

    def get_tool_entities(self) -> list[ToolEntity]:
        """获取提供商所有的工具"""
        return list(self.tool_entity_map.values())

    def _provider_init(self):
        """服务提供商初始化函数"""
        # 1. 获取当前类的路径，计算到对应服务提供商的地址/路径
        current_path = os.path.abspath(__file__)  # 获取当前文件所在路径
        entities_path = os.path.dirname(current_path)  # 获取当前文件夹路径
        provider_path = os.path.join(os.path.dirname(entities_path), "providers", self.name)

        # 2. 组装获取position.yaml数据
        positions_yaml_path = os.path.join(provider_path, "positions.yaml")
        with open(positions_yaml_path, encoding="utf-8") as f:
            positions_yaml_data = yaml.safe_load(f)

        # 3. 循环读取位置信息，并获取提供商的工具名字
        for tool_name in positions_yaml_data:
            # 4. 获取工具的yaml数据
            tool_yaml_path = os.path.join(provider_path, f"{tool_name}.yaml")
            with open(tool_yaml_path, encoding="utf-8") as f:
                tool_yaml_data = yaml.safe_load(f)

            # 5. 将工具信息实体赋值填充到tool_entity_map中
            self.tool_entity_map[tool_name] = ToolEntity(**tool_yaml_data)

            # 6. 将工具函数映射填充到tool_func_map中
            self.tool_func_map[tool_name] = dynamic_import(
                f"internal.core.tools.builtin_tools.providers.{self.name}",
                tool_name
            )
