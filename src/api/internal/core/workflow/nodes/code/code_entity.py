from pydantic import Field

from internal.core.workflow.entities.variable_entity import VariableEntity
from internal.core.workflow.nodes.base_node import BaseNodeData

"""默认代码"""
DEFAULT_CODE = """
def main(params):
    return params
"""


class CodeNodeData(BaseNodeData):
    """py代码执行节点数据"""
    code: str = DEFAULT_CODE  # 需要执行的py代码
    inputs: list[VariableEntity] = Field(default_factory=dict)  # 输入变量列表
    outputs: list[VariableEntity] = Field(default_factory=dict)  # 输出变量列表
