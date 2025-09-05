import time
from typing import Optional, Any
from uuid import UUID

from flask import Flask
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from pydantic import PrivateAttr

from internal.core.workflow.entities.workflow_entity import WorkflowState
from internal.core.workflow.nodes.base_node import BaseNode
from .dataset_retrieval_entity import DatasetRetrievalNodeData
from ...entities.node_entity import NodeResult, NodeStatus
from ...utils.helper import extract_variables_from_state


class DatasetRetrievalNode(BaseNode):
    """知识库检索节点"""

    node_data: DatasetRetrievalNodeData
    _retrieval_tool: BaseTool = PrivateAttr(None)

    def __init__(self,
                 *args: Any,
                 flask_app: Flask,
                 account_id: UUID,
                 **kwargs: Any):
        super().__init__(*args, **kwargs)
        from app.http.module import injector
        from internal.service import RetrievalService
        retrieval_service = injector.get(RetrievalService)

        self._retrieval_tool = retrieval_service.create_langchain_tool_from_search(
            flask_app=flask_app,
            dataset_ids=self.node_data.dataset_ids,
            account_id=account_id,
            **self.node_data.retrieval_config.dict()
        )

    def invoke_inner(self, state: WorkflowState, config: Optional[RunnableConfig] = None) -> WorkflowState:
        """知识库检索节点调用函数，执行响应的知识库检索后返回"""
        start_at = time.perf_counter()
        inputs_dict = extract_variables_from_state(self.node_data.inputs, state)

        combine_documents = self._retrieval_tool.invoke(inputs_dict)

        outputs = {}
        if self.node_data.outputs:
            outputs[self.node_data.outputs[0].name] = combine_documents
        else:
            outputs["combine_documents"] = combine_documents

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
