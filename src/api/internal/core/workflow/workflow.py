from typing import Any, Optional, AsyncIterator

from flask import current_app
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.utils import Input, Output
from langchain_core.tools import BaseTool
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import PrivateAttr, Field, create_model, BaseModel

from internal.exception import ValidateErrorException
from .entities.node_entity import NodeType
from .entities.variable_entity import VARIABLE_TYPE_MAP
from .entities.workflow_entity import WorkflowConfig, WorkflowState
from .nodes import (StartNode,
                    EndNode,
                    TemplateTransformNode,
                    DatasetRetrievalNode,
                    CodeNode,
                    ToolNode,
                    HttpRequestNode,
                    LLMNode,
                    QuestionClassifierNode,
                    QuestionClassifierNodeData,
                    IterationNode, ToolLLMNode)

NodeClasses = {
    NodeType.START: StartNode,
    NodeType.END: EndNode,
    NodeType.TEMPLATE_TRANSFORM: TemplateTransformNode,
    NodeType.DATASET_RETRIEVAL: DatasetRetrievalNode,
    NodeType.CODE: CodeNode,
    NodeType.TOOL: ToolNode,
    NodeType.HTTP_REQUEST: HttpRequestNode,
    NodeType.LLM: LLMNode,
    NodeType.QUESTION_CLASSIFIER: QuestionClassifierNode,
    NodeType.ITERATION: IterationNode,
    NodeType.TOOL_LLM: ToolLLMNode
}


class Workflow(BaseTool):
    """工作流langchain工具类"""
    _workflow_config: WorkflowConfig = PrivateAttr(None)
    _workflow: CompiledStateGraph = PrivateAttr(None)
    _base_model_func: Any = PrivateAttr(None)

    def __init__(self, workflow_config: WorkflowConfig, base_model_func, **kwargs: Any):
        super().__init__(
            name=workflow_config.name,
            description=workflow_config.description,
            args_schema=self._build_args_schema(workflow_config),
            **kwargs
        )
        self._base_model_func = base_model_func
        self._workflow_config = workflow_config
        self._workflow = self._build_workflow()

    def get_workflow_config(self):
        return self._workflow_config

    @classmethod
    def _build_args_schema(cls, workflow_config: WorkflowConfig) -> type[BaseModel]:
        """构建输入参数结构体"""
        fields = {}
        inputs = next(
            (node.inputs for node in workflow_config.nodes if node.node_type == NodeType.START),
            []
        )
        # 循环处理输入信息并创建字段映射
        for input in inputs:
            field_name = input.name
            field_type = VARIABLE_TYPE_MAP.get(input.type, str)
            field_required = input.required
            field_description = input.description

            fields[field_name] = (
                field_type if field_required else Optional[field_type],
                Field(description=field_description)
            )
        return create_model("DynamicModel", **fields)

    def _build_workflow(self) -> CompiledStateGraph:
        graph = StateGraph(WorkflowState)

        nodes = self._workflow_config.nodes
        edges = self._workflow_config.edges
        _kwargs = {"listen": self._on_node_exec}
        for node in nodes:
            node_flag = f"{node.node_type.value}_{node.id}"
            if node.node_type == NodeType.START:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.START](node_data=node, **_kwargs)
                )
            elif node.node_type == NodeType.LLM:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.LLM](node_data=node, **_kwargs)
                )
            elif node.node_type == NodeType.TEMPLATE_TRANSFORM:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.TEMPLATE_TRANSFORM](node_data=node, **_kwargs)
                )
            elif node.node_type == NodeType.DATASET_RETRIEVAL:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.DATASET_RETRIEVAL](
                        flask_app=current_app._get_current_object(),
                        account_id=self._workflow_config.account_id,
                        node_data=node, **_kwargs)
                )
            elif node.node_type == NodeType.TOOL:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.TOOL](node_data=node, **_kwargs)
                )
            elif node.node_type == NodeType.CODE:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.CODE](node_data=node, **_kwargs)
                )
            elif node.node_type == NodeType.HTTP_REQUEST:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.HTTP_REQUEST](node_data=node, **_kwargs)
                )
            elif node.node_type == NodeType.END:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.END](node_data=node, **_kwargs)
                )
            elif node.node_type == NodeType.QUESTION_CLASSIFIER:
                # 问题分类节点为条件边对应的节点，可以添加一个虚拟起始节点并返回空字典什么都不处理，让条件边可以快速找到起点
                graph.add_node(node_flag, lambda state: {"node_results": []})
                # 添加虚拟终止节点（每个分类一个节点）并返回空字典什么都不处理，让意图节点实现并行运行
                assert isinstance(node, QuestionClassifierNodeData)
                for item in node.classes:
                    graph.add_node(
                        f"qc_source_handle_{str(item.source_handle_id)}",
                        lambda state: {"node_results": []}
                    )
                graph.add_conditional_edges(
                    node_flag,
                    NodeClasses[NodeType.QUESTION_CLASSIFIER](node_data=node, base_model_func=self._base_model_func,
                                                              **_kwargs)
                )
            elif node.node_type == NodeType.ITERATION:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.ITERATION](node_data=node, base_model_func=self._base_model_func, **_kwargs)
                )
            elif node.node_type == NodeType.TOOL_LLM:
                graph.add_node(
                    node_flag,
                    NodeClasses[NodeType.TOOL_LLM](node_data=node, **_kwargs)
                )
            else:
                raise ValidateErrorException(f"{node.node_type} 工作流节点类型错误，请核实后重试")
        start_node = ""
        end_node = ""
        parallel_edges = {}  # key:终点；value:起点列表
        non_parallel_nodes = []  # 用于存储不能并行执行的节点列表信息(主要用来处理意图节点的虚拟起点和终点)
        for edge in edges:
            source_node = f"{edge.source_type.value}_{edge.source}"
            target_node = f"{edge.target_type.value}_{edge.target}"

            # 特殊处理意图识别节点
            if edge.source_type == NodeType.QUESTION_CLASSIFIER:
                # 更新意图识别的起点，使用虚拟节点进行拼接
                source_node = f"qc_source_handle_{str(edge.source_handle_id)}"
                non_parallel_nodes.extend([source_node, target_node])

            if target_node not in parallel_edges:
                parallel_edges[target_node] = [source_node]
            else:
                parallel_edges[target_node].append(source_node)

            if edge.source_type == NodeType.START:
                start_node = f"{edge.source_type.value}_{edge.source}"
            if edge.target_type == NodeType.END:
                end_node = f"{edge.target_type.value}_{edge.target}"

        graph.set_entry_point(start_node)
        graph.set_finish_point(end_node)

        # 8 循环遍历合并边 key:终点；value:起点列表
        for target_node, source_nodes in parallel_edges.items():
            source_nodes_temp = [*source_nodes]
            for item in non_parallel_nodes:
                if item in source_nodes_temp:
                    source_nodes_temp.remove(item)
                    graph.add_edge(item, target_node)

            graph.add_edge(source_nodes_temp, target_node)

        return graph.compile()

    def _on_node_exec(self, node_result):
        pass

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        result = self._workflow.invoke({"inputs": kwargs})
        return result.get("outputs", {})

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:
        result = await self._workflow.ainvoke({"inputs": kwargs})
        return result.get("outputs", {})

    async def astream(
            self,
            input: Input,
            config: Optional[RunnableConfig] = None,
            **kwargs: Optional[Any],
    ) -> AsyncIterator[Output]:
        """流式输出每个节点对应的结果"""
        wf_state = {"inputs": input}
        async for chunk in self._workflow.astream(wf_state):
            yield chunk
