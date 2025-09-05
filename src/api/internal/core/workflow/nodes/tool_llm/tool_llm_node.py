import json
import time
from typing import Any, Optional

from jinja2 import Template
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Input, Output
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import PrivateAttr

from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.workflow.entities.node_entity import NodeResult, NodeStatus
from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes import BaseNode
from internal.core.workflow.utils.helper import extract_variables_from_state
from internal.exception import FailException
from internal.lib.helper import check_http_server
from internal.model import ApiTool, McpTool
from .tool_llm_entity import ToolLLMNodeData


class McpToolInfo:
    url: str
    id: str

    def __init__(self, url: str, id: str):
        self.url = url
        self.id = id


class ToolLLMNode(BaseNode):
    """基于LLM的工具执行节点"""
    node_data: ToolLLMNodeData
    _tools: list[BaseTool] = PrivateAttr(None)
    _mcp_tools: list[McpToolInfo] = PrivateAttr(None)

    def __init__(self, *args, **kwargs: Any):
        super().__init__(*args, **kwargs)
        from app.http.module import injector
        from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
        from pkg.sqlalchemy import SQLAlchemy
        from internal.core.tools.api_tools.providers import ApiProviderManager
        builtin_provider_manager = injector.get(BuiltinProviderManager)
        db = injector.get(SQLAlchemy)
        api_provider_manager = injector.get(ApiProviderManager)

        self._tools = []
        self._mcp_tools = []

        for tool_arg in self.node_data.tools:
            if tool_arg.tool_type == "builtin_tool":
                # 内置工具
                _tool = builtin_provider_manager.get_tool(tool_arg.provider_id, tool_arg.tool_id)
                if _tool:
                    self._tools.append(_tool(**tool_arg.params))
            elif tool_arg.tool_type == "api_tool":
                # api插件
                api_tool = db.session.query(ApiTool).filter(
                    ApiTool.provider_id == tool_arg.provider_id,
                    ApiTool.name == tool_arg.tool_id
                ).one_or_none()
                if api_tool:
                    _tool = api_provider_manager.get_tool(
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
                    self._tools.append(_tool)
            elif tool_arg.tool_type == "mcp_tool":
                mcp_tool = db.session.query(McpTool).filter(
                    McpTool.name == tool_arg.tool_id
                ).one_or_none()
                if mcp_tool:
                    _mcp_tool = McpToolInfo(
                        url=mcp_tool.parameters.get("host", ""),
                        id=str(mcp_tool.id)
                    )
                    # 处理Mcp服务提供的工具，需要检测Mcp服务是否正常
                    if _mcp_tool.url and check_http_server(_mcp_tool.url):
                        self._mcp_tools.append(_mcp_tool)

    def invoke_inner(
            self, input: Input, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> Output:
        pass

    async def ainvoke_inner(
            self, state: WorkflowState, config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> Output:
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
        gathered = None
        is_first_chunk = True
        if not self._mcp_tools is None and len(self._mcp_tools) > 0:
            mcp_servers = {}
            for mcp in self._mcp_tools:
                mcp_servers[f'mcp_host_{mcp.id}'] = {
                    "url": mcp.url,
                    "transport": "sse"
                }
            async with MultiServerMCPClient(mcp_servers) as client:
                all_tool_infos = client.get_tools()
                if self._tools and len(self._tools) > 0:
                    all_tool_infos.extend(self._tools)
                llm_tool = llm.bind_tools(all_tool_infos)
                for chunk in llm_tool.stream(prompt_value):
                    if is_first_chunk:
                        gathered = chunk
                        is_first_chunk = False
                    else:
                        gathered += chunk
        elif not self._tools is None and len(self._tools) > 0:
            # 处理一般内置工具
            llm_tool = llm.bind_tools(self._tools)
            all_tool_infos = self._tools
            for chunk in llm_tool.stream(prompt_value):
                if is_first_chunk:
                    gathered = chunk
                    is_first_chunk = False
                else:
                    gathered += chunk
        else:
            raise FailException("没有配置可执行的工具")

        messages = None
        if hasattr(gathered, "tool_calls") and len(gathered.tool_calls) > 0:
            tools = gathered.tool_calls
            messages = await self.exec_tools(tools, all_tool_infos)
        # 5. 提取并构建输出数据结构
        content = ""
        if not messages is None and len(messages):
            content = '\n'.join([msg.content for msg in messages])
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

    @classmethod
    async def exec_tools(cls, tool_calls: list, all_tool_infos: list):
        messages = []
        tools_by_name = {tool.name: tool for tool in all_tool_infos}
        for tool_call in tool_calls:
            try:
                tool = tools_by_name[tool_call["name"]]
                tool_result = await tool.ainvoke(tool_call["args"])
            except Exception as e:
                tool_result = f"工具执行出错：{str(e)}"
            messages.append(ToolMessage(
                tool_call_id=tool_call["id"],
                content=json.dumps(tool_result),
                name=tool_call["name"]
            ))
        return messages
