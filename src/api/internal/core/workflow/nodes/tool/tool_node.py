import json
import time
from typing import Optional, Any

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.workflow.entities.node_entity import NodeStatus, NodeResult
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import NotFoundException, FailException
from internal.model import ApiTool
from .tool_entity import ToolNodeData


class ToolNode(BaseNode):
    """扩展插件节点"""
    node_data: ToolNodeData
    _tool: BaseTool = PrivateAttr(None)

    def __init__(self, *args, **kwargs: Any):
        super().__init__(*args, **kwargs)
        from app.http.module import injector
        if self.node_data.tool_type == "builtin_tool":
            from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
            builtin_provider_manager = injector.get(BuiltinProviderManager)
            # 调用内置提供者获取工具
            _tool = builtin_provider_manager.get_tool(self.node_data.provider_id, self.node_data.tool_id)
            if not _tool:
                raise NotFoundException("该内置插件扩展不存在，请核实后重试")
            self._tool = _tool(**self.node_data.params)
        else:
            # api工具
            from pkg.sqlalchemy import SQLAlchemy
            db = injector.get(SQLAlchemy)

            api_tool = db.session.query(ApiTool).filter(
                ApiTool.provider_id == self.node_data.provider_id,
                ApiTool.name == self.node_data.tool_id
            ).one_or_none()
            if not api_tool:
                raise NotFoundException("该API扩展插件不存在，请核实后重试")

            # 7 导入API插件提供者
            from internal.core.tools.api_tools.providers import ApiProviderManager
            api_provider_manager = injector.get(ApiProviderManager)

            self._tool = api_provider_manager.get_tool(
                ToolEntity(
                    id=str(api_tool.id),
                    name=api_tool.name,
                    url=api_tool.url,
                    method=api_tool.method,
                    description=api_tool.description,
                    headers=api_tool.provider.headers,
                    parameters=api_tool.parameters
                )
            )

    def invoke_inner(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        try:
            result = self._tool.invoke(inputs_dict)
        except Exception as e:
            raise FailException(f"扩展插件执行失败 {e}")

        if not isinstance(result, str):
            result = json.dumps(result, ensure_ascii=False)

        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = result
        else:
            outputs["text"] = result

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
