from typing import Any

from internal.core.workflow.entities.variable_entity import VariableEntity, VARIABLE_TYPE_MAP, VariableValueType, \
    VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState


def extract_variables_from_state(variables: list[VariableEntity], state: WorkflowState) -> dict[str, Any]:
    """从状态中提取变量映射值信息"""
    variables_dict = {}

    for variable in variables:
        variable_type_cls = VARIABLE_TYPE_MAP.get(variable.type)

        if variable.value.type == VariableValueType.LITERAL:
            """直接输入，直接输入"""
            variables_dict[variable.name] = variable_type_cls(variable.value.content)
        else:
            """引用or生成，遍历点获取数据"""
            for node_result in state["node_results"]:
                if node_result.node_data.id == variable.value.content.ref_node_id:
                    # 提取数据并完成数据强制转换
                    variables_dict[variable.name] = variable_type_cls(node_result.outputs.get(
                        variable.value.content.ref_var_name,
                        VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(variable.type)
                    ))

    return variables_dict
