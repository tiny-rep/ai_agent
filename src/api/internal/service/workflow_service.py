import json
import logging
import queue
import time
import uuid
from dataclasses import dataclass
from queue import Queue
from threading import Thread
from typing import Any, Generator
from uuid import UUID

from asgiref.sync import async_to_sync
from flask import request, current_app, Flask
from injector import inject
from sqlalchemy import desc

from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.workflow import Workflow as WorkflowTool
from internal.core.workflow.entities.edge_entity import BaseEdgeData
from internal.core.workflow.entities.node_entity import NodeType, BaseNodeData
from internal.core.workflow.entities.workflow_entity import WorkflowConfig
from internal.core.workflow.nodes import (
    CodeNodeData,
    DatasetRetrievalNodeData,
    EndNodeData,
    StartNodeData,
    HttpRequestNodeData,
    LLMNodeData,
    TemplateTransformNodeData,
    ToolNodeData, QuestionClassifierNodeData, IterationNodeData, ToolLLMNodeData
)
from internal.entity.workflow_entity import DEFAULT_WORKFLOW_CONFIG, WorkflowStatus, WorkflowResultStatus
from internal.entity.workflow_entity import WorkflowDebugGeneratorItemInfo
from internal.exception import ValidateErrorException, NotFoundException, ForbiddenException, FailException
from internal.lib.helper import convert_model_to_dict
from internal.model import Account, Workflow, Dataset, ApiTool, WorkflowResult, McpTool
from internal.schema.workflow_schema import CreateWorkflowReq, GetWorkflowsWithPageReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .language_model_service import LanguageModelService


@inject
@dataclass
class WorkflowService(BaseService):
    """工作流服务"""
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    language_model_service: LanguageModelService

    def create_workflow(self, req: CreateWorkflowReq, account: Account):
        """创建工作流"""
        check_workflow = self.db.session.query(Workflow).filter(
            Workflow.tool_call_name == req.tool_call_name.data.strip(),
            Workflow.account_id == account.id
        ).one_or_none()
        if check_workflow:
            raise ValidateErrorException(f"在当前账号下已创建[{req.tool_call_name.data}]工作流，不支持重名")

        return self.create(Workflow, **{
            **req.data,
            **DEFAULT_WORKFLOW_CONFIG,
            "account_id": account.id,
            "is_debug_passed": False,
            "status": WorkflowStatus.DRAFT,
            "tool_call_name": req.tool_call_name.data.strip()
        })

    def get_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        workflow = self.get(Workflow, workflow_id)

        if not workflow:
            raise NotFoundException("该工作流不存在，请核实后重试")

        if workflow.account_id != account.id:
            raise ForbiddenException("当前账号无权限访问该应用，请核实后重试")

        return workflow

    def delete_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        workflow = self.get_workflow(workflow_id, account)

        self.delete(workflow)

        return workflow

    def update_workflow(self, workflow_id: UUID, account: Account, **kwargs) -> Workflow:
        workflow = self.get_workflow(workflow_id, account)

        check_workflow = self.db.session.query(Workflow).filter(
            Workflow.tool_call_name == kwargs.get("tool_call_name", "").strip(),
            Workflow.account_id == account.id,
            Workflow.id != workflow.id
        ).one_or_none()
        if check_workflow:
            raise ValidateErrorException(f"在当前账号下已创建[{kwargs.get('tool_call_name', '')}]工作流，不支持重名")

        self.update(workflow, **kwargs)

        return workflow

    def get_workflow_with_page(self, req: GetWorkflowsWithPageReq, account: Account
                               ) -> tuple[list[Workflow], Paginator]:
        paginator = Paginator(db=self.db, req=req)

        filters = [Workflow.account_id == account.id]

        if req.search_word.data:
            filters.append(Workflow.name.ilike(f"%{req.search_word.data}%"))

        if req.status.data:
            filters.append(Workflow.status == req.status.data)

        # 3 分页查询
        workflows = paginator.paginate(
            self.db.session.query(Workflow).filter(*filters).order_by(desc("created_at"))
        )
        return workflows, paginator

    def update_draft_graph(self, workflow_id: UUID, draft_graph: dict[str, Any], account: Account) -> Workflow:
        workflow = self.get_workflow(workflow_id, account)

        validate_draft_graph = self._validate_graph(workflow_id, draft_graph, account)
        self.update(workflow, **{
            "draft_graph": validate_draft_graph,
            "is_debug_passed": False
        })

        return workflow

    def get_draft_graph(self, workflow_id: UUID, account: Account) -> dict[str, Any]:
        workflow = self.get_workflow(workflow_id, account)

        draft_graph = workflow.draft_graph
        validate_draft_graph = self._validate_graph(workflow_id, draft_graph, account)

        # 3 循环遍历节点信息，为工具节点/知识库节点附加元数据
        for node in validate_draft_graph["nodes"]:
            if node.get("node_type") == NodeType.TOOL:
                # 4. 判断工具类型
                if node.get("tool_type") == "builtin_tool":
                    # 5. 节点类型为工具，则附加工具的名称、图标、参数等额外信息
                    provider = self.builtin_provider_manager.get_provider(node.get("provider_id"))
                    if not provider:
                        continue

                    # 6. 获取提供者下的工具实体，并检测是否存在
                    tool_entity = provider.get_tool_entity(node.get("tool_id"))
                    if not tool_entity:
                        continue

                    # 7. 判断工具的params和草稿中的params是否一致，如果不一致全部重置为默认值（或者考虑删除这个工具的引用）
                    param_keys = set([param.name for param in tool_entity.params])
                    params = node.get("params")
                    if set(params.keys()) - param_keys:
                        params = {
                            param.name: param.default
                            for param in tool_entity.params
                            if param.default is not None
                        }
                    # 8. 数据校验成功附加展示信息
                    provider_entity = provider.provider_entity
                    node["meta"] = {
                        "type": "builtin_tool",
                        "provider": {
                            "id": provider_entity.name,
                            "name": provider_entity.name,
                            "label": provider_entity.label,
                            "icon": f"{request.scheme}://{request.host}/builtin_tools/{provider_entity.name}/icon",
                            "description": provider_entity.description
                        },
                        "tool": {
                            "id": tool_entity.name,
                            "name": tool_entity.name,
                            "label": tool_entity.label,
                            "description": tool_entity.description,
                            "params": params
                        }
                    }
                elif node.get("tool_type") == 'api_tool':
                    # 9. 查询数据库获取对应的工具记录，并检测是否存在
                    tool_record = self.db.session.query(ApiTool).filter(
                        ApiTool.provider_id == node.get("provider_id"),
                        ApiTool.name == node.get("tool_id"),
                        ApiTool.account_id == account.id
                    ).one_or_none()
                    if not tool_record:
                        continue
                    provider = tool_record.provider
                    # 10 组装api工具展示信息
                    node["meta"] = {
                        "type": "api_tool",
                        "provider": {
                            "id": str(provider.id),
                            "name": provider.name,
                            "label": provider.name,
                            "icon": provider.icon,
                            "description": provider.description
                        },
                        "tool": {
                            "id": str(tool_record.id),
                            "name": tool_record.name,
                            "label": tool_record.name,
                            "description": tool_record.description,
                            "params": {}
                        }
                    }
                else:
                    node["meta"] = {
                        "type": "api_tool",
                        "provider": {
                            "id": "",
                            "name": "",
                            "label": "",
                            "icon": "",
                            "description": ""
                        },
                        "tool": {
                            "id": "",
                            "name": "",
                            "label": "",
                            "description": "",
                            "params": {}
                        }
                    }

            elif node.get("node_type") == NodeType.DATASET_RETRIEVAL:
                # 知识库检测节点
                datasets = self.db.session.query(Dataset).filter(
                    Dataset.id.in_(node.get("dataset_ids", [])),
                    Dataset.account_id == account.id
                ).all()
                datasets = datasets[:5]
                node["dataset_ids"] = [str(dataset.id) for dataset in datasets]
                node["meta"] = {
                    "datasets": [{
                        "id": dataset.id,
                        "name": dataset.name,
                        "icon": dataset.icon,
                        "description": dataset.description
                    } for dataset in datasets]
                }
            # 6.[功能升级] 检查迭代节点工作流配置
            elif node.get("node_type") == NodeType.ITERATION:
                workflows = self.db.session.query(Workflow).filter(
                    Workflow.id.in_(node.get("workflow_ids", [])),
                    Workflow.account_id == account.id,
                    Workflow.status == WorkflowStatus.PUBLISHED,
                ).all()
                workflows = workflows[:1]
                node["workflow_ids"] = [str(workflow.id) for workflow in workflows]
                node["meta"] = {
                    "workflows": [{
                        "id": workflow.id,
                        "name": workflow.name,
                        "icon": workflow.icon,
                        "description": workflow.description,
                    } for workflow in workflows]
                }
            elif node.get("node_type") == NodeType.TOOL_LLM:
                tool_metas = []
                tools = node.get("tools")
                if len(tools) > 0:
                    for tool in tools:
                        if tool.get("tool_type") == "builtin_tool":
                            provider = self.builtin_provider_manager.get_provider(tool.get("provider_id"))
                            if not provider:
                                continue

                            # 6. 获取提供者下的工具实体，并检测是否存在
                            tool_entity = provider.get_tool_entity(tool.get("tool_id"))
                            if not tool_entity:
                                continue

                            # 7. 判断工具的params和草稿中的params是否一致，如果不一致全部重置为默认值（或者考虑删除这个工具的引用）
                            param_keys = set([param.name for param in tool_entity.params])
                            params = tool.get("params")
                            if set(params.keys()) - param_keys:
                                params = {
                                    param.name: param.default
                                    for param in tool_entity.params
                                    if param.default is not None
                                }
                            # 8. 数据校验成功附加展示信息
                            provider_entity = provider.provider_entity
                            meta = {
                                "type": "builtin_tool",
                                "provider": {
                                    "id": provider_entity.name,
                                    "name": provider_entity.name,
                                    "label": provider_entity.label,
                                    "icon": f"{request.scheme}://{request.host}/builtin-tools/{provider_entity.name}/icon",
                                    "description": provider_entity.description
                                },
                                "tool": {
                                    "id": tool_entity.name,
                                    "name": tool_entity.name,
                                    "label": tool_entity.label,
                                    "description": tool_entity.description,
                                    "params": params
                                }
                            }
                            tool_metas.append(meta)
                        elif tool.get("tool_type") == "api_tool":
                            # 9. 查询数据库获取对应的工具记录，并检测是否存在
                            tool_record = self.db.session.query(ApiTool).filter(
                                ApiTool.provider_id == tool.get("provider_id"),
                                ApiTool.name == tool.get("tool_id"),
                                ApiTool.account_id == account.id
                            ).one_or_none()
                            if not tool_record:
                                continue
                            provider = tool_record.provider
                            # 10 组装api工具展示信息
                            meta = {
                                "type": "api_tool",
                                "provider": {
                                    "id": str(provider.id),
                                    "name": provider.name,
                                    "label": provider.name,
                                    "icon": provider.icon,
                                    "description": provider.description
                                },
                                "tool": {
                                    "id": str(tool_record.id),
                                    "name": tool_record.name,
                                    "label": tool_record.name,
                                    "description": tool_record.description,
                                    "params": {}
                                }
                            }
                            tool_metas.append(meta)
                        elif tool.get("tool_type") == "mcp_tool":
                            # 9. 查询数据库获取对应的Mcp记录，并检测是否存在
                            mcp_tool_record = self.db.session.query(McpTool).filter(
                                McpTool.name == tool.get("tool_id"),
                                McpTool.account_id == account.id
                            ).one_or_none()
                            if not mcp_tool_record:
                                continue
                            # 10 组装api工具展示信息
                            meta = {
                                "type": "mcp_tool",
                                "provider": {
                                    "id": str(mcp_tool_record.id),
                                    "name": mcp_tool_record.provider_name,
                                    "label": mcp_tool_record.provider_name,
                                    "icon": mcp_tool_record.icon,
                                    "description": ''
                                },
                                "tool": {
                                    "id": str(mcp_tool_record.id),
                                    "name": mcp_tool_record.name,
                                    "label": mcp_tool_record.name,
                                    "description": mcp_tool_record.description,
                                    "params": {}
                                }
                            }
                            tool_metas.append(meta)
                        else:
                            meta = {
                                "type": "api_tool",
                                "provider": {
                                    "id": "",
                                    "name": "",
                                    "label": "",
                                    "icon": "",
                                    "description": ""
                                },
                                "tool": {
                                    "id": "",
                                    "name": "",
                                    "label": "",
                                    "description": "",
                                    "params": {}
                                }
                            }
                            tool_metas.append(meta)
                node["metas"] = tool_metas

        return validate_draft_graph

    def debug_workflow(self, workflow_id: UUID, inputs: dict[str, Any], account: Account) -> Generator:
        """调试工作流API接口，流式事件输出"""
        workflow_info = self.get_workflow(workflow_id, account)
        _queue = Queue()

        async def handle_stream(workflow: Workflow, arg_inputs: dict[str, Any], account_id: UUID, flask_app: Flask):
            with flask_app.app_context():
                workflow_tool = WorkflowTool(workflow_config=WorkflowConfig(
                    account_id=account_id,
                    name=workflow.tool_call_name,
                    description=workflow.description,
                    nodes=workflow.draft_graph.get("nodes", []),
                    edges=workflow.draft_graph.get("edges", [])
                ), base_model_func=self.language_model_service.load_default_language_model_with_config)
                # 3. 定义变量存储所有节点运行结果
                node_results = []
                # 5. 调用stream服务获取工具信息
                try:
                    async for chunk in workflow_tool.astream(arg_inputs):
                        # 5. chunk的格式为:{"node_name":WorkflowState}，所以需要节点响应结构的第1个key
                        first_key = next(iter(chunk))
                        # 6. 取出名节点的运行结果
                        # 6.1 因为存在虚拟节点，所以需要判断是否执行当前循环
                        if len(chunk[first_key]["node_results"]) == 0:
                            continue
                        node_result = chunk[first_key]["node_results"][0]
                        node_result_dict = convert_model_to_dict(node_result)
                        node_results.append(node_result_dict)
                        # 7. 组装响应数据并流式事件输出
                        data = {
                            "id": str(uuid.uuid4()),
                            **node_result_dict
                        }
                        _queue.put(
                            WorkflowDebugGeneratorItemInfo("running", f"event: workflow\ndata:{json.dumps(data)}\n\n"))

                    _queue.put(WorkflowDebugGeneratorItemInfo("end", node_results))

                except Exception as e:
                    logging.exception("执行工作流发生错误, 错误信息: %(error)s", {"error": e})
                    _queue.put(WorkflowDebugGeneratorItemInfo("error", ""))

        def listen_stream() -> Generator:
            """sse发送数据"""
            # 4. 添加数据库工作流运行结果记录
            workflow_result = self.create(WorkflowResult, **{
                "app_id": None,
                "account_id": account.id,
                "workflow_id": workflow_info.id,
                "graph": workflow_info.draft_graph,
                "state": [],
                "latency": 0,
                "status": WorkflowResultStatus.RUNNING
            })
            start_at = time.perf_counter()
            while True:
                try:
                    item = _queue.get(timeout=1)
                    if item.stage != 'end' and item.stage != 'error':
                        yield item.chunk
                    else:
                        node_results = item.chunk
                        if item.stage == 'end':
                            # 7. 流式输出完毕后，半结果存储到数据库中
                            self.update(workflow_result, **{
                                "status": WorkflowResultStatus.SUCCEEDED,
                                "state": node_results,
                                "latency": (time.perf_counter() - start_at)
                            })
                            self.update(workflow_info, **{
                                "is_debug_passed": True
                            })
                        elif item.stage == "error":
                            self.update(workflow_result, **{
                                "status": WorkflowResultStatus.FAILED,
                                "state": node_results,
                                "latency": (time.perf_counter() - start_at)
                            })
                        break
                except queue.Empty:
                    continue

        sync_handle_stream = async_to_sync(handle_stream)
        thread = Thread(
            target=sync_handle_stream,
            args=(workflow_info, inputs, account.id, current_app._get_current_object())
        )
        thread.start()
        return listen_stream()

    def publish_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """发布指定的工作流"""
        # 1. 获取工作流
        workflow = self.get_workflow(workflow_id, account)

        # 2. 校验工作流是否为调试模式
        if workflow.is_debug_passed is False:
            raise FailException("该工作流未调试通过，请调试通过后发布")

        # 3. 使用workflowconfig二次校验，如果校验失败则不发布
        try:
            WorkflowConfig(
                account_id=account.id,
                name=workflow.tool_call_name,
                description=workflow.description,
                nodes=workflow.draft_graph.get("nodes", []),
                edges=workflow.draft_graph.get("edges", [])
            )
        except Exception:
            self.update(workflow, **{
                "is_debug_passed": False
            })
            raise ValidateErrorException("工作流配置校验失败，请核实后重试")

        # 4. 更新工作流发布状态
        self.update(workflow, **{
            "graph": workflow.draft_graph,
            "status": WorkflowStatus.PUBLISHED,
            "is_debug_passed": False
        })

        return workflow

    def cancel_publish_workflow(self, workflow_id: UUID, account: Account) -> Workflow:
        """取消工作流的发布"""
        workflow = self.get_workflow(workflow_id, account)

        if workflow.status != WorkflowStatus.PUBLISHED:
            raise FailException("该工作流未发布无法取消发布")

        self.update(workflow, **{
            "graph": {},
            "status": WorkflowStatus.DRAFT,
            "is_debug_passed": False
        })

        return workflow

    def _validate_graph(self, workflow_id: UUID, graph: dict[str, Any], account: Account) -> dict[str, Any]:
        """校验传递的graph信息，涵盖nodes和edges对应的数据，该函数使用相对宽松的校验方式，并且因为是草稿，不需要校验节点与边的关系"""
        # 1.提取nodes和edges数据
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        # 2.构建节点类型与节点数据类映射
        node_data_classes = {
            NodeType.START: StartNodeData,
            NodeType.END: EndNodeData,
            NodeType.LLM: LLMNodeData,
            NodeType.TEMPLATE_TRANSFORM: TemplateTransformNodeData,
            NodeType.DATASET_RETRIEVAL: DatasetRetrievalNodeData,
            NodeType.CODE: CodeNodeData,
            NodeType.TOOL: ToolNodeData,
            NodeType.HTTP_REQUEST: HttpRequestNodeData,
            NodeType.QUESTION_CLASSIFIER: QuestionClassifierNodeData,
            NodeType.ITERATION: IterationNodeData,
            NodeType.TOOL_LLM: ToolLLMNodeData
        }

        # 3.循环校验nodes中各个节点对应的数据
        node_data_dict: dict[UUID, BaseNodeData] = {}
        start_nodes = 0
        end_nodes = 0
        for node in nodes:
            try:
                # 4.校验传递的node数据是不是字典，如果不是则跳过当前数据
                if not isinstance(node, dict):
                    raise ValidateErrorException("工作流节点数据类型出错，请核实后重试")

                # 5.提取节点的node_type类型，并判断类型是否正确
                node_type = node.get("node_type", "")
                node_data_cls = node_data_classes.get(node_type, None)
                if node_data_cls is None:
                    raise ValidateErrorException("工作流节点类型出错，请核实后重试")

                # 6.实例化节点数据类型，如果出错则跳过当前数据
                node_data = node_data_cls(**node)

                # 7.判断节点id是否唯一，如果不唯一，则将当前节点清除
                if node_data.id in node_data_dict:
                    raise ValidateErrorException("工作流节点id必须唯一，请核实后重试")

                # 8.判断节点title是否唯一，如果不唯一，则将当前节点清除
                if any(item.title.strip() == node_data.title.strip() for item in node_data_dict.values()):
                    raise ValidateErrorException("工作流节点title必须唯一，请核实后重试")

                # 9.对特殊节点进行判断，涵盖开始/结束/知识库检索/工具
                if node_data.node_type == NodeType.START:
                    if start_nodes >= 1:
                        raise ValidateErrorException("工作流中只允许有1个开始节点")
                    start_nodes += 1
                elif node_data.node_type == NodeType.END:
                    if end_nodes >= 1:
                        raise ValidateErrorException("工作流中只允许有1个结束节点")
                    end_nodes += 1
                elif node_data.node_type == NodeType.DATASET_RETRIEVAL:
                    # 10.剔除关联知识库列表中不属于当前账户的数据
                    datasets = self.db.session.query(Dataset).filter(
                        Dataset.id.in_(node_data.dataset_ids[:5]),
                        Dataset.account_id == account.id,
                    ).all()
                    node_data.dataset_ids = [dataset.id for dataset in datasets]
                # 11.[升级更新] 判断类型为迭代节点，剔除不属于当前账户并且未发布的工作流
                elif node_data.node_type == NodeType.ITERATION:
                    workflows = self.db.session.query(Workflow).filter(
                        Workflow.id.in_(node_data.workflow_ids[:1]),
                        Workflow.account_id == account.id,
                        Workflow.status == WorkflowStatus.PUBLISHED,
                    ).all()
                    # 11.[升级更新] 剔除当前工作流，迭代节点不能内嵌本身（这块还可以继续升级，双方不能内嵌）
                    node_data.workflow_ids = [workflow.id for workflow in workflows if workflow.id != workflow_id]

                # 11.将数据添加到node_data_dict中
                node_data_dict[node_data.id] = node_data
            except Exception as e:
                print(e)
                continue

        # 14.循环校验edges中各个节点对应的数据
        edge_data_dict: dict[UUID, BaseEdgeData] = {}
        for edge in edges:
            try:
                # 15.边类型为非字典则抛出错误，否则转换成BaseEdgeData
                if not isinstance(edge, dict):
                    raise ValidateErrorException("工作流边数据类型出错，请核实后重试")
                edge_data = BaseEdgeData(**edge)

                # 16.校验边edges的id是否唯一
                if edge_data.id in edge_data_dict:
                    raise ValidateErrorException("工作流边数据id必须唯一，请核实后重试")

                # 17.校验边中的source/target/source_type/target_type必须和nodes对得上
                if (
                        edge_data.source not in node_data_dict
                        or edge_data.source_type != node_data_dict[edge_data.source].node_type
                        or edge_data.target not in node_data_dict
                        or edge_data.target_type != node_data_dict[edge_data.target].node_type
                ):
                    raise ValidateErrorException("工作流边起点/终点对应的节点不存在或类型错误，请核实后重试")

                # 18.校验边Edges里的边必须唯一(source+target必须唯一)
                # 18.1 条件判断变更：source+target+source+handle_id必须唯一
                if any(
                        (item.source == edge_data.source
                         and item.target == edge_data.target
                         and item.source_handle_id == edge_data.source_handle_id)
                        for item in edge_data_dict.values()
                ):
                    raise ValidateErrorException("工作流边数据不能重复添加")

                # 19.基础数据校验通过，将数据添加到edge_data_dict中
                edge_data_dict[edge_data.id] = edge_data
            except Exception:
                continue

        return {
            "nodes": [convert_model_to_dict(node_data) for node_data in node_data_dict.values()],
            "edges": [convert_model_to_dict(edge_data) for edge_data in edge_data_dict.values()],
        }
