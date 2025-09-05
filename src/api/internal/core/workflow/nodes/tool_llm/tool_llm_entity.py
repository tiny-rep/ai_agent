from typing import Any, Literal

from pydantic import Field, BaseModel, field_validator

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType
from internal.entity.app_entity import DEFAULT_APP_CONFIG


class ToolLLMItemConfig(BaseModel):
    class Config:
        populate_by_name = True
        
    tool_type: Literal["builtin_tool", "api_tool", "mcp_tool", ""] = Field(alias="type")  # 工具类型
    provider_id: str  # 工具提供者id
    tool_id: str  # 工具id
    params: dict[str, Any] = Field(default_factory=dict)  # 内置工具设置参数


class ToolLLMNodeData(BaseNodeData):
    """基于LLM的工具执行节点"""
    prompt: str  # LLM模型提示词
    language_model_config: dict[str, Any] = Field(
        alias="model_config",
        default_factory=lambda: DEFAULT_APP_CONFIG["model_config"]
    )  # LLM配置信息
    tools: list[ToolLLMItemConfig] = Field(default_factory=list)  # 工具列表
    inputs: list[VariableEntity] = Field(default_factory=list)  # 输入变量列表
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("outputs", mode="before")
    def validate_outputs(cls, outputs: list[VariableEntity]):
        return [
            VariableEntity(name="text", value={"type": VariableValueType.GENERATED})
        ]
