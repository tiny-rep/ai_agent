from dataclasses import dataclass
from typing import Any, Union
from uuid import UUID

from injector import inject
from langchain_core.tools import BaseTool

from internal.core.language_model.entities.model_entity import ModelParameterType
from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.tools.api_tools.providers import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.core.workflow import Workflow as WorkflowTool
from internal.core.workflow.entities.workflow_entity import WorkflowConfig
from internal.entity.app_entity import DEFAULT_APP_CONFIG
from internal.entity.workflow_entity import WorkflowStatus
from internal.lib.helper import datetime_to_timestamp, get_value_type
from internal.model import ApiTool, Dataset, AppConfig, AppConfigVersion, App, AppDatasetJoin, Workflow, McpTool
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .language_model_service import LanguageModelService


@inject
@dataclass
class AppConfigService(BaseService):
    """应用配置服务"""
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    api_provider_manager: ApiProviderManager
    language_model_manager: LanguageModelManager
    language_model_service: LanguageModelService

    def get_draft_app_config(self, app: App) -> dict[str, Any]:
        """获取应用的草稿配置信息"""
        # 1. 获取草稿
        draft_app_config = app.draft_app_config

        # 2 model_config校验
        validate_model_config = self._process_and_validate_model_config(draft_app_config.model_config)
        if draft_app_config.model_config != validate_model_config:
            self.update(draft_app_config, model_config=validate_model_config)

        # 3. 工具处理
        tools, validate_tools = self._process_and_validate_tools(draft_app_config.tools)

        # 4. 判断是否需要更新草稿配置中的工具列表信息
        if draft_app_config.tools != validate_tools:
            self.update(draft_app_config, tools=validate_tools)

        # 5. 知识信息
        datasets, validate_datasets = self._process_and_validate_datasets(draft_app_config.datasets)
        if draft_app_config.datasets != validate_datasets:
            self.update(draft_app_config, datasets=validate_datasets)

        # 6. workflow 校验
        workflows, validate_workflows = self._process_and_validate_workflows(draft_app_config.workflows)
        if set(validate_workflows) != set(draft_app_config.workflows):
            self.update(draft_app_config, workflows=validate_workflows)

        # 7. mcp 校验
        mcps, validate_mcps = self._process_and_validate_mcps(draft_app_config.mcps)
        if set(validate_mcps) != set(draft_app_config.mcps):
            self.update(draft_app_config, mcps=validate_mcps)

        return self._process_and_transformer_app_config(validate_model_config, tools, workflows, datasets, mcps,
                                                        draft_app_config)

    def get_app_config(self, app: App) -> dict[str, Any]:
        """获取应用配置信息"""
        # 1. 获取配置信息
        app_config = app.app_config

        # 2 model_config校验
        validate_model_config = self._process_and_validate_model_config(app_config.model_config)
        if app_config.model_config != validate_model_config:
            self.update(app_config, model_config=validate_model_config)

        # 3. 工具处理
        tools, validate_tools = self._process_and_validate_tools(app_config.tools)

        # 4. 判断是否需要更新草稿配置中的工具列表信息
        if app_config.tools != validate_tools:
            self.update(app_config, tools=validate_tools)

        # 5. 知识信息
        app_dataset_joins = app_config.app_dataset_joins
        origin_datasets = [str(app_dataset_join.dataset_id) for app_dataset_join in app_dataset_joins]
        datasets, validate_datasets = self._process_and_validate_datasets(origin_datasets)

        for dataset_id in (set(origin_datasets) - set(validate_datasets)):
            with self.db.auto_commit():
                self.db.session.query(AppDatasetJoin).filter(AppDatasetJoin.dataset_id == dataset_id).delete()

        # 6. workflow 校验
        workflows, validate_workflows = self._process_and_validate_workflows(app_config.workflows)
        if set(validate_workflows) != set(app_config.workflows):
            self.update(app_config, workflows=validate_workflows)

        # 7. mcp 校验
        mcps, validate_mcps = self._process_and_validate_mcps(app_config.mcps)
        if set(validate_mcps) != set(app_config.mcps):
            self.update(app_config, mcps=validate_mcps)

        return self._process_and_transformer_app_config(validate_model_config, tools, workflows, datasets, mcps,
                                                        app_config)

    def get_langchain_tools_by_tools_config(self, tools_config: list[dict], account_id: str) -> list[BaseTool]:
        """工具配置转换为langchain工具列表"""
        tools = []
        for tool in tools_config:
            # 2.根据不同的工具类型执行不同的操作
            if tool["type"] == "builtin_tool":
                # 3.内置工具，通过builtin_provider_manager获取工具实例
                builtin_tool = self.builtin_provider_manager.get_tool(
                    tool["provider"]["id"],
                    tool["tool"]["name"]
                )
                if not builtin_tool:
                    continue
                args = {**tool["tool"]["params"], "account_id": account_id}

                tools.append(builtin_tool(**args))
            else:
                # 4.API工具，首先根据id找到ApiTool记录，然后创建示例
                api_tool = self.get(ApiTool, tool["tool"]["id"])
                if not api_tool:
                    continue
                tools.append(
                    self.api_provider_manager.get_tool(
                        ToolEntity(
                            id=str(api_tool.id),
                            name=api_tool.name,
                            url=api_tool.url,
                            method=api_tool.method,
                            description=api_tool.description,
                            headers=api_tool.provider.headers,
                            parameters=api_tool.parameters,
                        )
                    )
                )

        return tools

    def get_langchain_tools_by_workflow_ids(self, workflow_ids: list[UUID]) -> list[BaseTool]:
        """将流程转换为langchain工具"""
        workflow_records = self.db.session.query(Workflow).filter(
            Workflow.id.in_(workflow_ids),
            Workflow.status == WorkflowStatus.PUBLISHED
        ).all()

        workflows = []
        for workflow_record in workflow_records:
            try:
                workflow_tool = WorkflowTool(
                    workflow_config=WorkflowConfig(
                        account_id=workflow_record.account_id,
                        name=f"wf_{workflow_record.tool_call_name}",
                        cn_name=workflow_record.name,
                        description=workflow_record.description,
                        nodes=workflow_record.graph.get("nodes", []),
                        edges=workflow_record.graph.get("edges", [])
                    ), base_model_func=self.language_model_service.load_default_language_model_with_config)
                workflows.append(workflow_tool)
            except Exception as e:
                print(e)
                continue

        return workflows

    def get_mcps_by_mcp_ids(self, mcp_ids: list[UUID]) -> list[dict]:
        """根据Id返回Mcp配置列表"""
        mcp_records = self.db.session.query(McpTool).filter(
            McpTool.id.in_(mcp_ids)
        ).all()

        mcps = []
        for mcp_record in mcp_records:
            mcps.append({
                "id": mcp_record.id,
                "transport_type": mcp_record.transport_type,
                **mcp_record.parameters
            })
        return mcps

    @classmethod
    def _process_and_transformer_app_config(cls,
                                            model_config: dict[str, Any],
                                            tools: list[dict],
                                            workflows: list[dict],
                                            datasets: list[dict],
                                            mcps: list[dict],
                                            app_config: Union[AppConfig, AppConfigVersion]
                                            ) -> dict[str, Any]:
        """组装配置字典"""
        return {
            "id": str(app_config.id),
            "model_config": model_config,
            "dialog_round": app_config.dialog_round,
            "preset_prompt": app_config.preset_prompt,
            "tools": tools,
            "workflows": workflows,
            "datasets": datasets,
            "mcps": mcps,
            "retrieval_config": app_config.retrieval_config,
            "long_term_memory": app_config.long_term_memory,
            "opening_statement": app_config.opening_statement,
            "opening_questions": app_config.opening_questions,
            "speech_to_text": app_config.speech_to_text,
            "text_to_speech": app_config.text_to_speech,
            "suggested_after_answer": app_config.suggested_after_answer,
            "review_config": app_config.review_config,
            "updated_at": datetime_to_timestamp(app_config.updated_at),
            "created_at": datetime_to_timestamp(app_config.created_at),
        }

    def _process_and_validate_tools(self, origin_tools: list[dict]) -> tuple[list[dict], list[dict]]:
        """工具处理和校验"""
        validate_tools = []
        tools = []
        for tool in origin_tools:
            if tool["type"] == "builtin_tool":
                # 5. 查询内置工具提供者，并检测是否存在
                provider = self.builtin_provider_manager.get_provider(tool["provider_id"])
                if not provider:
                    continue

                # 6. 获取提供者下的工具实体，并检测是否存在
                tool_entity = provider.get_tool_entity(tool["tool_id"])
                if not tool_entity:
                    continue
                # 7. 判断工具的params与草稿的params是否一致，不一致直接用默认值
                params_keys = set([param.name for param in tool_entity.params])
                params = tool["params"]
                if set(tool["params"].keys()) - params_keys:
                    params = {
                        param.name: param.default
                        for param in tool_entity.params
                        if param.default is not None
                    }
                # 8 数据存在，并且参数已通过校验，可以将数据添加到validate_tools
                validate_tools.append({**tool, "params": params})

                # 9. 组装内置工具展示信息
                provider_entity = provider.provider_entity
                tools.append({
                    "type": "builtin_tool",
                    "provider": {
                        "id": provider_entity.name,
                        "name": provider_entity.name,
                        "label": provider_entity.label,
                        "icon": f"/api/builtin-tools/{provider_entity.name}/icon",
                        "description": provider_entity.description
                    },
                    "tool": {
                        "id": tool_entity.name,
                        "name": tool_entity.name,
                        "label": tool_entity.label,
                        "description": tool_entity.description,
                        "params": tool["params"]
                    }
                })
            elif tool["type"] == "api_tool":
                # 10 API工具
                tool_record = self.db.session.query(ApiTool).filter(
                    ApiTool.provider_id == tool["provider_id"],
                    ApiTool.name == tool["tool_id"]
                ).one_or_none()
                if not tool_record:
                    continue

                # 11 数据校验通过，添加到validate_tools中
                validate_tools.append(tool)

                # 12 组装API工具展示信息
                provider = tool_record.provider
                tools.append({
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
                })

        return tools, validate_tools

    def _process_and_validate_datasets(self, origin_datasets: list[dict]) -> tuple[list[dict], list[dict]]:
        """处理和校验 知识库"""
        datasets = []
        dataset_records = self.db.session.query(Dataset).filter(Dataset.id.in_(origin_datasets)).all()
        dataset_dict = {str(dataset_record.id): dataset_record for dataset_record in dataset_records}
        dataset_sets = set(dataset_dict.keys())

        # 16 计算存在的知识库id列表，为了保留原始顺序，使用列表循环的方式来判断
        validate_datasets = [dataset_id for dataset_id in origin_datasets if dataset_id in dataset_sets]

        # 18 循环获取知识库数据
        for dataset_id in validate_datasets:
            dataset = dataset_dict.get(str(dataset_id))
            datasets.append({
                "id": str(dataset.id),
                "name": dataset.name,
                "icon": dataset.icon,
                "description": dataset.description
            })
        return datasets, validate_datasets

    def _process_and_validate_model_config(self, origin_model_config: dict[str, Any]) -> dict[str, Any]:
        """model_config校验"""
        if not isinstance(origin_model_config, dict):
            return DEFAULT_APP_CONFIG["model_config"]

        # 2. 提取model_config中的provider、model、parameters对应的信息
        model_config = {
            "provider": origin_model_config.get("provider", ""),
            "model": origin_model_config.get("model", ""),
            "parameters": origin_model_config.get("parameters", {})
        }

        # 3. 判断provider是否存
        if not model_config["provider"] or not isinstance(model_config["provider"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        provider = self.language_model_manager.get_provider(model_config["provider"])
        if not provider:
            return DEFAULT_APP_CONFIG["model_config"]

        # 4. 判断model是否存
        if not model_config["model"] or not isinstance(model_config["model"], str):
            return DEFAULT_APP_CONFIG["model_config"]
        model_entity = provider.get_model_entity(model_config["model"])
        if not model_entity:
            return DEFAULT_APP_CONFIG["model_config"]

        # 5. 判断parameters是否正常
        if not isinstance(model_config["parameters"], dict):
            model_config["parameters"] = {
                parameter.name: parameter.default for parameter in model_entity.parameters
            }
        # 6. 处理parameter参数，剔除多余的，缺少的补充上
        parameters = {}
        for parameter in model_entity.parameters:
            # 7. 从model_config中获取参数值，如果不存在用默认值
            parameter_value = model_config["parameters"].get(parameter.name, parameter.default)

            # 8. 判断是否必填
            if parameter.required:
                # 9. 参数必填，则值不允许为None，如果为None则设置为默认值
                if parameter_value is None:
                    parameter_value = parameter.default
                else:
                    # 10 值非空则校验数据类型是否正确
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default
            else:
                # 11. 参数非必埴，数据非空的情况下要校验
                if parameter_value is not None:
                    if get_value_type(parameter_value) != parameter.type.value:
                        parameter_value = parameter.default

            # 12. 判断参数是否存在options，如果上辈子在则数值必须在options中选择
            if parameter.options and parameter_value not in parameter.options:
                parameter_value = parameter.default

            # 13. 参数类型为int/float，如果存在min/max时需要校验
            if parameter.type in [ModelParameterType.INT, ModelParameterType.FLOAT] and parameter_value is not None:
                # 14. 校验数值的min/max
                if (
                        (parameter.min and parameter_value < parameter.min)
                        or (parameter.max and parameter_value > parameter.max)
                ):
                    parameter_value = parameter.default

            parameters[parameter.name] = parameter_value

        model_config["parameters"] = parameters

        return model_config

    def _process_and_validate_workflows(self, origin_workflows: list[UUID]) -> tuple[list[dict], list[UUID]]:
        """校验工作流配置信息"""
        workflows = []
        workflow_records = self.db.session.query(Workflow).filter(
            Workflow.id.in_(origin_workflows),
            Workflow.status == WorkflowStatus.PUBLISHED
        ).all()
        workflow_dict = {str(workflow_record.id): workflow_record for workflow_record in workflow_records}
        workflow_sets = set(workflow_dict.keys())

        # 2. 计算存在的工作流id列表，为了保留原始顺序，使用列表循环的方式判断
        validate_workflows = [workflow_id for workflow_id in origin_workflows if workflow_id in workflow_sets]

        # 3. 循环获取工作流数据
        for workflow_id in validate_workflows:
            workflow = workflow_dict.get(str(workflow_id))
            workflows.append({
                "id": str(workflow_id),
                "name": workflow.name,
                "icon": workflow.icon,
                "description": workflow.description
            })
        return workflows, validate_workflows

    def _process_and_validate_mcps(self, origin_mcps: list[UUID]) -> tuple[list[dict], list[UUID]]:
        """校验mcp配置信息"""
        mcps = []
        mcps_records = self.db.session.query(McpTool).filter(
            McpTool.id.in_(origin_mcps)
        ).all()
        mcp_dict = {str(mcp_record.id): mcp_record for mcp_record in mcps_records}
        mcp_sets = set(mcp_dict.keys())

        # 2. 计算存在的mcp id列表，为了保留原始顺序，使用列表循环的方式判断
        validate_mcps = [mcp_id for mcp_id in origin_mcps if mcp_id in mcp_sets]

        # 3. 循环获取mcp数据
        for mcp_id in validate_mcps:
            mcp = mcp_dict.get(str(mcp_id))
            mcps.append({
                "id": str(mcp_id),
                "name": mcp.name,
                "icon": mcp.icon,
                "description": mcp.description
            })
        return mcps, validate_mcps
