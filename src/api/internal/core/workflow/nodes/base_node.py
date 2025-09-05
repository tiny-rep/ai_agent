from abc import ABC, abstractmethod
from typing import Optional, Any

from langchain_core.runnables import RunnableSerializable, RunnableConfig
from langchain_core.runnables.config import run_in_executor

from internal.core.workflow.entities.node_entity import BaseNodeData
from internal.core.workflow.entities.workflow_entity import WorkflowState


class BaseNode(RunnableSerializable, ABC):
    """工作流基类"""
    node_data: BaseNodeData
    _node_listen: Any

    def __init__(self, *args, **kwargs: Any):
        super().__init__(*args, **kwargs)
        if "listen" in kwargs:
            self._node_listen = kwargs.get("listen")
        else:
            self._node_listen = self._default_node_listen

    def _default_node_listen(self, info):
        pass

    def invoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        result = self.invoke_inner(state, config)
        self._node_listen(result)
        return result

    @abstractmethod
    def invoke_inner(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        pass

    async def ainvoke(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        result = await self.ainvoke_inner(state, config)
        self._node_listen(result)
        return result

    async def ainvoke_inner(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        return await run_in_executor(config, self.invoke_inner, state, config)
