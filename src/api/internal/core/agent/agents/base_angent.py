import uuid
from abc import abstractmethod
from threading import Thread
from typing import Any, Optional, Iterator

from asgiref.sync import async_to_sync
from flask import current_app
from langchain_core.load import Serializable
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph.state import CompiledStateGraph
from pydantic import PrivateAttr, ConfigDict

from internal.core.agent.entities.agnet_entity import AgentConfig, AgentState
from internal.core.agent.entities.queue_entity import AgentResult, AgentThought, QueueEvent
from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.exception import FailException
from internal.lib.helper import check_http_server
from .agent_queue_manager import AgentQueueManager


class BaseAgent(Serializable, Runnable):
    model_config = ConfigDict(
        arbitrary_types_allowed=True  # 字段允许接收任意类型，且不需要校验器
    )

    """agent基类"""
    llm: BaseLanguageModel
    agent_config: AgentConfig
    _agent: CompiledStateGraph = PrivateAttr(None)
    _agent_queue_manager: AgentQueueManager = PrivateAttr(None)

    def __init__(self,
                 llm: BaseLanguageModel,
                 agent_config: AgentConfig,
                 *args,
                 **kwargs
                 ):
        super().__init__(*args, name="agent", llm=llm, agent_config=agent_config, **kwargs)
        self._agent = self._build_agent()
        self._agent_queue_manager = AgentQueueManager(
            user_id=agent_config.user_id,
            invoke_form=agent_config.invoke_from
        )

    @abstractmethod
    def _build_agent(self) -> CompiledStateGraph:
        """构建智能体子函数，由子类实现"""
        raise NotImplementedError("未实现")

    def invoke(self, input: AgentState, config: Optional[RunnableConfig] = None) -> AgentResult:
        """块内容响应，一次生成完整内容后返回"""

        content = input["messages"][0].content
        query = ""
        image_urls = []
        if isinstance(content, str):
            query = content
        elif isinstance(content, list):
            query = content[0]["text"]
            image_urls = [chunk["image_url"]["url"] for chunk in content if chunk.get("type") == "image_url"]

        agent_result = AgentResult(query=query, image_urls=image_urls)
        agent_thoughts = {}

        for agent_thought in self.stream(input, config):
            # 1. 提取事件Id并转换为字符串
            event_id = str(agent_thought.id)

            # 2. 排除ping事件，其他都记录
            if agent_thought.event != QueueEvent.PING:
                # 3. 单独处理agent_message事件，此事件为叠加
                if agent_thought.event == QueueEvent.AGENT_MESSAGE or agent_thought.event == QueueEvent.AGENT_THINK:
                    # 4. 检测是否已存储事件
                    if event_id not in agent_thoughts:
                        # 5. 初始化事件
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 6. 叠加消息事件
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(
                            update={
                                "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                                "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                                "latency": agent_thought.latency
                            })
                        # 7. 更新智能体消息答案
                        agent_result.answer += agent_thought.answer
                else:
                    # 8. 处理其他类型的智能体事件，均为覆盖
                    agent_thoughts[event_id] = agent_thought

                    # 9. 处理异常类消息
                    if agent_thought.event in [QueueEvent.STOP, QueueEvent.TIMEOUT, QueueEvent.ERROR]:
                        agent_result.status = agent_thought.event
                        agent_result.error = agent_thought.observation if agent_thought.event == QueueEvent.ERROR else ""
        # 10. 推理字典转换成列表并存储
        agent_result.agent_thoughts = [agent_thought for agent_thought in agent_thoughts.values()]

        # 11. 完善message
        agent_result.message = next(
            (agent_thought.message for agent_thought in agent_thoughts.values()
             if agent_thought.event == QueueEvent.AGENT_MESSAGE),
            []
        )

        # 12. 更新总体耗时
        agent_result.latency = sum(agent_thought.latency for agent_thought in agent_thoughts.values())

        return agent_result

    def stream(self,
               input: AgentState,
               config: Optional[RunnableConfig] = None,
               **kwargs: Optional[Any]) -> Iterator[AgentThought]:
        """流式输出，每个Not节点或者LLM每生成一个token时则会返回相应的内容"""
        if not self._agent:
            raise FailException("智能体未成功构建，请核实后重试")

        flask_app = current_app._get_current_object()
        input["task_id"] = input.get("task_id", uuid.uuid4())
        input["history"] = input.get("history", [])
        input["iteration_count"] = input.get("iteration_count", 0)

        # todo 实现 sse 的mcp集成与接入
        async def exec_chat_with_mcp(arg):
            mcp_servers = {}
            has_mcp_server = False
            if self.agent_config.mcps:
                for mcp in self.agent_config.mcps:
                    if check_http_server(mcp["host"]):
                        has_mcp_server = True
                        mcp_servers[f'mcp_host_{mcp["id"]}'] = {
                            "url": mcp["host"],
                            "transport": "sse"
                        }
            with flask_app.app_context():
                if has_mcp_server:
                    async with MultiServerMCPClient(mcp_servers) as client:
                        mcp_tools = client.get_tools()
                        self.agent_config.tools.extend(mcp_tools)
                        return await self._agent.ainvoke(arg)
                else:
                    return await self._agent.ainvoke(arg)

        thread = Thread(
            target=async_to_sync(exec_chat_with_mcp),
            args=(input,)
        )
        thread.start()

        yield from self._agent_queue_manager.listen(input["task_id"])

    @property
    def agent_queue_manager(self) -> AgentQueueManager:
        return self._agent_queue_manager
