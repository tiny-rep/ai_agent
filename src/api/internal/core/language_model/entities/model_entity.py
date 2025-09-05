from abc import ABC
from enum import Enum
from typing import Optional, Any

from langchain_core.language_models import BaseLanguageModel as LCBaseLanguageModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field


class DefaultModelParameterName(str, Enum):
    """默认的参数名称，一般是所有LLM都有的一些参数"""
    TEMPERATURE = "temperature"  # 温度
    TOP_P = "top_p"  # 核采样率
    PRESENCE_PENALTY = "presence_penalty"  # 存在惩罚
    FREQUENCY_PENALTY = "frequency_penalty"  # 频率惩罚
    MAX_TOKENS = "max_tokens"  # 要生成的内容的最大tokens数


class ModelType(str, Enum):
    """模型类型枚举"""
    CHAT = "chat"  # 聊天模型
    COMPLETION = "completion"  # 文本生成模型


class ModelParameterType(str, Enum):
    """模型参数类型"""
    FLOAT = "float"
    INT = "int"
    STRING = "string"
    BOOLEAN = "boolean"


class ModelParameterOption(BaseModel):
    """模型参数选项配置模型"""
    label: str
    value: str


class ModelParameter(BaseModel):
    """模型参数实体信息"""
    name: str = ""  # 参数名字
    label: str = ""  # 参数标签
    type: ModelParameterType = ModelParameterType.STRING  # 参数的类型
    help: str = ""  # 帮助信息
    required: bool = False  # 是否必填
    default: Optional[Any] = None  # 默认参数值
    min: Optional[float] = None  # 最小值
    max: Optional[float] = None  # 最大值
    precision: int = 2  # 保留小数位数
    options: list[ModelParameterOption] = Field(default_factory=list)  # 可选的参数配置


class ModelFeature(str, Enum):
    """模型特性，包含：工具调用，智能体推理，图片输入"""
    TOOL_CALL = "tool_call"  # 工具调用
    AGENT_THOUGHT = "agent_thought"  # 推理
    IMAGE_INPUT = "image_input"  # 图片输入，多模态大语言模型


class ModelEntity(BaseModel):
    """语言模型实体，记录模型的相关信息"""
    model_name: str = Field(default="", alias="model")  # 模型名字，使用model作为别名
    label: str = ""  # 模型标签
    model_type: ModelType = ModelType.CHAT  # 模型类型
    features: list[ModelFeature] = Field(default_factory=list)  # 模型特征信息
    context_window: int = 0  # 上下文窗口长度（输入+输出）
    max_output_tokens: int = 0  # 最大输出内容长度（输出）
    attributes: dict[str, Any] = Field(default_factory=dict)  # 模型固定属性字典
    parameters: list[ModelParameter] = Field(default_factory=list)  # 模型参数字段规则列表，用于记录模型的配置参数
    metadata: dict[str, Any] = Field(default_factory=dict)  # 模型元数据，用于存储模型的额外数据，如：价格，词表等信息


class BaseLanguageModel(LCBaseLanguageModel, ABC):
    """基础语言模型"""
    features: list[ModelFeature] = Field(default_factory=list)  # 模型特性
    metadata: dict[str, Any] = Field(default_factory=dict)  # 模型元数据信息

    def get_pricing(self) -> tuple[float, float, float]:
        """获取LLM的价格信息，输出格式（输入价格、输出价格、单位）"""
        input_price = self.metadata.get("pricing", {}).get("input", 0.0)
        output_price = self.metadata.get("pricing", {}).get("output", 0.0)
        unit = self.metadata.get("pricing", {}).get("unit", 0.0)
        return input_price, output_price, unit

    def convert_to_human_message(self, query: str, image_urls: list[str] = None) -> HumanMessage:
        """根据模型特征，转换Human消息是来普通的，还是多模态消息"""
        # todo: 多模型图片加特征，有是通过url访问图片（如：GPT-4o），有的时候通过文件路径（如：llava），要做兼容处理

        if image_urls is None or len(image_urls) == 0 or ModelFeature.IMAGE_INPUT not in self.features:
            return HumanMessage(content=query)

        # 多模态模型消息格式
        return HumanMessage(content=[
            {"type": "text", "text": query},
            *[{"type": "image_url", "image_url": {"url": image_url}} for image_url in image_urls]
        ])
