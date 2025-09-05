import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.variable_entity import VARIABLE_TYPE_DEFAULT_VALUE_MAP
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.nodes.start.start_entity import StartNodeData
from internal.exception import FailException


class StartNode(BaseNode):
    """开始节点"""
    node_data: StartNodeData

    def invoke_inner(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        # 1. 提取节点数据中的僌数据
        start_at = time.perf_counter()
        inputs = self.node_data.inputs

        # 2. 循环处理输入数据，并提取需要的数据，同时检测必填是否传递，如果未传递报错
        outputs = {}
        for input in inputs:
            input_value = state["inputs"].get(input.name, None)

            # 3. 检测字段是否必填
            if input_value is None:
                if input.required:
                    raise FailException(f"工作流参数生成出错：{input.name}")
                else:
                    input_value = VARIABLE_TYPE_DEFAULT_VALUE_MAP.get(input.type)
            # 4. 提取出输出数据
            outputs[input.name] = input_value

        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=state["inputs"],
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at)
                )
            ]
        }
