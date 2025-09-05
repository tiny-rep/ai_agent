import time
from typing import Optional, Any

from jinja2 import Template
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Input, Output

from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.nodes.llm.llm_entity import LLMNodeData
from internal.core.workflow.utils.helper import extract_variables_from_state


class LLMNode(BaseNode):
    """大模型处理节点"""
    node_data: LLMNodeData

    def invoke_inner(
            self, input: Input, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> Output:
        pass

    async def ainvoke_inner(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        # 2. 模板处理
        template = Template(self.node_data.prompt)
        prompt_value = template.render(**inputs_dict)

        # 3. 根据配置创建LLM实例，等待接入多LLM
        from app.http.module import injector
        from internal.service import LanguageModelService
        language_model_service = injector.get(LanguageModelService)
        llm = language_model_service.load_language_model(self.node_data.language_model_config)

        # 4. 使用stream代替invoke，避免接口长时间未响应
        content = ""
        for chunk in llm.stream(prompt_value):
            content += chunk.content
        # 5. 提取并构建输出数据结构
        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = content
        else:
            outputs["output"] = content

        # 6 返回响应结构
        return {
            "node_results": [
                NodeResult(
                    node_data=self.node_data,
                    status=NodeStatus.SUCCEEDED,
                    inputs=inputs_dict,
                    outputs=outputs,
                    latency=(time.perf_counter() - start_at)
                )
            ]
        }
