import time
from typing import Optional

from langchain_core.runnables import RunnableConfig

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.nodes.end.end_entity import EndNodeData
from internal.core.workflow.utils.helper import extract_variables_from_state


class EndNode(BaseNode):
    """结束节点"""
    node_data: EndNodeData

    def invoke_inner(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        # 1. 提取节点中需要输出的数据
        start_at = time.perf_counter()
        outputs_dict = extract_variables_from_state(self.node_data.outputs, state)

        # 2. 组装状态并返回
        return {
            "outputs": outputs_dict,
            "node_results": [NodeResult(
                node_data=self.node_data,
                status=NodeStatus.SUCCEEDED,
                inputs={},
                outputs=outputs_dict,
                latency=(time.perf_counter() - start_at)
            )]
        }
