from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from internal.core.workflow.entities.variable_entity import VariableEntity, VariableValueType, VariableType
from internal.core.workflow.nodes.base_node import BaseNodeData
from internal.entity.dataset_entity import RetrievalStrategy
from internal.exception import FailException


class RetrievalConfig(BaseModel):
    """检索配置"""
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.SEMANTIC  # 检索策略
    k: int = 4  # 最大召回数量
    score: float = 0  # 得分阀值


class DatasetRetrievalNodeData(BaseNodeData):
    """知识库检索节点数据"""
    dataset_ids: list[UUID]  # 关联知识库id列表
    retrieval_config: RetrievalConfig = RetrievalConfig()  # 检索配置
    inputs: list[VariableEntity] = Field(default_factory=dict)  # 输入变量信息
    outputs: list[VariableEntity] = Field(
        default_factory=lambda: [
            VariableEntity(name="combine_documents", value={"type": VariableValueType.GENERATED})
        ]
    )

    @field_validator("outputs", mode="before")
    def validate_outputs(cls, value: list[VariableEntity]):
        return [
            VariableEntity(name="combine_documents", value={"type": VariableValueType.GENERATED})
        ]

    @field_validator("inputs")
    def validate_inputs(cls, value: list[VariableEntity]):
        """验证输入变量列表"""
        # 1. 判断是否只有一个输入变量，如果有多个则抛出错误
        if len(value) != 1:
            raise FailException("知识库节点输入变量信息出错")
        # 2. 判断输入遍历那个的类型及字段名称是否出错
        query_input = value[0]
        if query_input.name != "query" or query_input.type != VariableType.STRING or query_input.required is False:
            raise FailException("知识库节点输入变量名字/变量类型/必填属性出错")
        return value
