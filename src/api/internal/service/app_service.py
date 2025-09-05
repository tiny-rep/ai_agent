import io
import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generator
from uuid import UUID

import requests
from flask import current_app
from injector import inject
from langchain_community.utilities.dalle_image_generator import DallEAPIWrapper
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableParallel
from langchain_openai import ChatOpenAI
from sqlalchemy import func, desc
from werkzeug.datastructures.file_storage import FileStorage

from internal.core.agent.agents import FunctionCallAgent, AgentQueueManager, ReactAgent
from internal.core.agent.entities.agnet_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model.entities.model_entity import ModelParameterType, ModelFeature
from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.core.memory import TokenBufferMemory
from internal.core.tools.api_tools.providers.api_provider_manager import ApiProviderManager
from internal.core.tools.builtin_tools.providers import BuiltinProviderManager
from internal.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from internal.entity.app_entity import AppStatus, AppConfigType, DEFAULT_APP_CONFIG, GENERATE_ICON_PROMPT_TEMPLATE
from internal.entity.audio_entity import ALLOWED_AUDIO_VOICES
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.entity.workflow_entity import WorkflowStatus
from internal.exception import NotFoundException, ForbiddenException, ValidateErrorException, FailException
from internal.lib.helper import remove_fields, get_value_type, generate_random_string
from internal.model import Account, AppConfigVersion, ApiTool, Dataset, Conversation, Message, AppConfig, \
    AppDatasetJoin, Workflow, McpTool
from internal.model.app import App
from internal.schema.app_schema import CreateAppReq, GetPublishHistoriesWithPageReq, \
    GetDebugConversationMessagesWithPageReq, GetAppsWithPageReq, DebugChatReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService
from .base_service import BaseService
from .conversation_service import ConversationService
from .cos_local_service import CosLocalService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService


@inject
@dataclass
class AppService(BaseService):
    """应用服务"""
    db: SQLAlchemy
    builtin_provider_manager: BuiltinProviderManager
    conversation_service: ConversationService
    api_provider_manager: ApiProviderManager
    retrieval_service: RetrievalService
    app_config_service: AppConfigService
    cos_service: CosLocalService
    language_model_service: LanguageModelService
    language_model_manager: LanguageModelManager

    def auto_create_app(self, name: str, description: str, account_id: UUID) -> None:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.8)
        dalle_api_wrapper = DallEAPIWrapper(model="dall-e-3", size="1024x1024")

        # 构建生成icon链
        generate_icon_chain = ChatPromptTemplate.from_template(
            GENERATE_ICON_PROMPT_TEMPLATE
        ) | llm | StrOutputParser() | dalle_api_wrapper.run

        # 构建生成prompt链
        generate_preset_prompt_chain = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", f"应用名称：{name}\n\n应用描述：{description}")
        ]) | llm | StrOutputParser()

        # 5. 创建并行链同时执行两条链
        generate_app_config_chain = RunnableParallel({
            "icon": generate_icon_chain,
            "preset_prompt": generate_preset_prompt_chain
        })
        app_config = generate_app_config_chain.invoke({"name": name, "description": description})

        # 下载Icon
        icon_response = requests.get(app_config.get("icon"))
        if icon_response.status_code == 200:
            icon_content = icon_response.content
        else:
            raise FailException("生成应用Icon图标出错")
        account = self.db.session.query(Account).get(account_id)
        upload_file = self.cos_service.upload_file(
            FileStorage(io.BytesIO(icon_content), filename="icon.png"),
            account,
            True
        )
        icon = self.cos_service.get_file_url(upload_file.key)

        # 7.开启数据库自动提交上下文
        with self.db.auto_commit():
            # 8.创建应用记录并刷新数据，从而可以拿到应用id
            app = App(
                account_id=account.id,
                name=name,
                icon=icon,
                description=description,
            )
            self.db.session.add(app)
            self.db.session.flush()

            # 9.添加草稿记录
            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **{
                    **DEFAULT_APP_CONFIG,
                    "preset_prompt": app_config.get("preset_prompt", ""),
                }
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            # 10.更新应用配置id
            app.draft_app_config_id = app_config_version.id

    def create_app(self, req: CreateAppReq, account: Account) -> App:
        """创建Agent应用"""
        with self.db.auto_commit():
            app = App(
                account_id=account.id,
                name=req.name.data,
                icon=req.icon.data,
                description=req.description.data,
                status=AppStatus.DRAFT
            )
            self.db.session.add(app)
            self.db.session.flush()

            app_config_version = AppConfigVersion(
                app_id=app.id,
                version=0,
                config_type=AppConfigType.DRAFT,
                **DEFAULT_APP_CONFIG
            )
            self.db.session.add(app_config_version)
            self.db.session.flush()

            app.draft_app_config_id = app_config_version.id
        return app

    def get_app(self, app_id: UUID, account: Account) -> App:
        app = self.get(App, app_id)

        if not app:
            raise NotFoundException("该应用不存在，请核实后重试")

        if app.account_id != account.id:
            raise ForbiddenException("当前账号无权限访问此应用，请核实后重试")

        return app

    def delete_app(self, app_id: UUID, account: Account) -> App:
        app = self.get_app(app_id, account)
        self.delete(app)
        return app

    def update_app(self, app_id: UUID, account: Account, **kwargs) -> App:
        app = self.get_app(app_id, account)
        self.update(app, **kwargs)
        return app

    def copy_app(self, app_id: UUID, account: Account) -> App:
        """复制App"""
        app = self.get_app(app_id, account)
        draft_app_config = app.draft_app_config

        # 2. 复制一份用来操作
        app_dict = app.__dict__.copy()
        draft_app_config_dict = draft_app_config.__dict__.copy()

        # 3. 剔除无用字段
        app_remove_fields = [
            "id", "app_config_id", "draft_app_config_id", "debug_conversation_id",
            "status", "updated_at", "created_at", "_sa_instance_state"
        ]
        draft_app_config_remove_fields = [
            "id", "app_id", "version", "updated_at", "created_at", "_sa_instance_state"
        ]
        remove_fields(app_dict, app_remove_fields)
        remove_fields(draft_app_config_dict, draft_app_config_remove_fields)

        with self.db.auto_commit():
            new_app = App(**app_dict, status=AppStatus.DRAFT)
            self.db.session.add(new_app)
            self.db.session.flush()

            new_draft_app_config = AppConfigVersion(
                **draft_app_config_dict,
                app_id=new_app.id,
                version=0
            )
            self.db.session.add(new_draft_app_config)
            self.db.session.flush()
            new_app.draft_app_config_id = new_draft_app_config.id

        return new_app

    def get_apps_with_page(self, req: GetAppsWithPageReq, account: Account) -> tuple[list[App], Paginator]:
        paginator = Paginator(db=self.db, req=req)

        filters = [App.account_id == account.id]
        if req.search_word.data:
            filters.append(App.name.ilike(f"%{req.search_word.data}%"))
        apps = paginator.paginate(
            self.db.session.query(App).filter(*filters).order_by(desc("created_at"))
        )
        return apps, paginator

    def get_draft_app_config(self, app_id: UUID, account: Account):
        """根据应用id，获取指定的应用草稿配置信息"""
        # 1. 获取应用
        app = self.get_app(app_id, account)
        return self.app_config_service.get_draft_app_config(app)

    def update_draft_app_config(self, app_id: UUID, draft_app_config: dict[str, Any], account: Account):
        """修改指定应用的最新草稿"""
        app = self.get_app(app_id, account)
        draft_app_config = self._validate_draft_app_config(draft_app_config, account)
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo: 使用server_onupdate，所以字段需要手动传递
            updated_at=datetime.now(),
            **draft_app_config,
        )

    def publish_draft_app_config(self, app_id: UUID, account: Account):
        """发布应用草稿配置为运行时配置"""
        app = self.get_app(app_id, account)
        draft_app_config = self.get_draft_app_config(app_id, account)

        # 2. 创建应用运行配置(暂时不删除历史的运行配置)
        app_config = self.create(
            AppConfig,
            app_id=app_id,
            model_config=draft_app_config["model_config"],
            dialog_round=draft_app_config["dialog_round"],
            preset_prompt=draft_app_config["preset_prompt"],
            tools=[
                {
                    "type": tool["type"],
                    "provider_id": tool["provider"]["id"],
                    "tool_id": tool["tool"]["name"],
                    "params": tool["tool"]["params"]
                }
                for tool in draft_app_config["tools"]
            ],
            workflows=[workflow["id"] for workflow in draft_app_config["workflows"]],
            retrieval_config=draft_app_config["retrieval_config"],
            long_term_memory=draft_app_config["long_term_memory"],
            opening_statement=draft_app_config["opening_statement"],
            opening_questions=draft_app_config["opening_questions"],
            speech_to_text=draft_app_config["speech_to_text"],
            text_to_speech=draft_app_config["text_to_speech"],
            suggested_after_answer=draft_app_config["suggested_after_answer"],
            review_config=draft_app_config["review_config"],
            mcps=[mcp["id"] for mcp in draft_app_config["mcps"]]
        )
        # 3. 更新应用关联的运行时配置以及状态
        self.update(app, app_config_id=app_config.id, status=AppStatus.PUBLISHED)

        # 4. 先删除原有的知识库关联记录
        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id
            ).delete()

        # 5 新增新的知识库关联记录
        for dataset in draft_app_config["datasets"]:
            self.create(AppDatasetJoin, app_id=app_id, dataset_id=dataset["id"])

        # 6 获取应用草稿记录、移除：id, version, config_type, updated_at, created_at字段
        draft_app_config_copy = app.draft_app_config.__dict__.copy()
        remove_field_names = ["id", "version", "config_type", "updated_at", "created_at", "_sa_instance_state"]
        remove_fields(
            draft_app_config_copy,
            remove_field_names
        )

        # 7. 获取当前最大的发布版本
        max_version = self.db.session.query(func.coalesce(func.max(AppConfigVersion.version), 0)).filter(
            AppConfigVersion.app_id == app_id,
            AppConfigVersion.config_type == AppConfigType.PUBLISHED
        ).scalar()

        # 8. 更新发布历史配置
        self.create(
            AppConfigVersion,
            version=max_version + 1,
            config_type=AppConfigType.PUBLISHED,
            **draft_app_config_copy
        )
        return app

    def cancel_publish_app_config(self, app_id: UUID, account: Account):
        """取消发布指定的应用配置"""
        app = self.get_app(app_id, account)

        if app.status != AppStatus.PUBLISHED:
            raise FailException("当前应用未发布，请核实后重试")
        self.update(app, status=AppStatus.DRAFT, app_config_id=None)

        with self.db.auto_commit():
            self.db.session.query(AppDatasetJoin).filter(
                AppDatasetJoin.app_id == app_id
            ).delete()

        return app

    def get_publish_histories_with_page(self, app_id: UUID, req: GetPublishHistoriesWithPageReq,
                                        account: Account) -> tuple[list[AppConfigVersion], Paginator]:
        """获取指定应用的发布历史配置列表信息"""
        # 1. 获取应用信息并验证权限
        self.get_app(app_id, account)

        paginator = Paginator(db=self.db, req=req)

        app_config_versions = paginator.paginate(
            self.db.session.query(AppConfigVersion).filter(
                AppConfigVersion.app_id == app_id,
                AppConfigVersion.config_type == AppConfigType.PUBLISHED
            ).order_by(desc("version"))
        )

        return app_config_versions, paginator

    def fallback_history_to_draft(self, app_id: UUID, app_config_version_id: UUID,
                                  account: Account) -> AppConfigVersion:
        """回退特定版本到草稿"""
        app = self.get_app(app_id, account)

        # 2. 查看指定版本配置Id
        app_config_version = self.get(AppConfigVersion, app_config_version_id)
        if not app_config_version:
            raise NotFoundException("该历史版本配置不存在，请核实后重试")

        # 3. 校验历史版本信息，剔除已删除：工具，知识库、工作流
        draft_app_config_dic = app_config_version.__dict__.copy()
        remove_field_names = ["id", "app_id", "version", "config_type", "updated_at", "created_at",
                              "_sa_instance_state"]
        remove_fields(draft_app_config_dic, remove_field_names)

        # 4. 校验历史版本配置信息
        draft_app_config_dic = self._validate_draft_app_config(draft_app_config_dic, account)

        # 5. 更新到草稿配置
        draft_app_config_record = app.draft_app_config
        self.update(
            draft_app_config_record,
            # todo: 更新时间补丁信息
            updated_at=datetime.now(),
            **draft_app_config_dic
        )
        return draft_app_config_record

    def get_debug_conversation_summary(self, app_id: UUID, account: Account) -> str:
        """获取指定应用的调度会话长期记忆信息"""
        app = self.get_app(app_id, account)

        draft_app_config = self.get_draft_app_config(app_id, account)

        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("该应用并未开启长期记忆，无法获取")
        return app.debug_conversation.summary

    def update_debug_conversation_summary(self, app_id: UUID, summary: str, account: Account) -> Conversation:
        """更新指定应用的调试长期记忆"""
        app = self.get_app(app_id, account)

        draft_app_config = self.get_draft_app_config(app_id, account)
        if draft_app_config["long_term_memory"]["enable"] is False:
            raise FailException("该应用并未开启长期记忆，无法获取")

        debug_conversation = app.debug_conversation
        self.update(debug_conversation, summary=summary)

        return debug_conversation

    def delete_debug_conversation(self, app_id: UUID, account: Account):
        """删除指定应用的调试会话"""
        app = self.get_app(app_id, account)

        # 2. 如果debug_conversation_id不存在，表示没有会话信息
        if not app.debug_conversation_id:
            return app

        # 3. 否则将debug_conversation_id的值重置为None
        self.update(app, debug_conversation_id=None)

        return app

    def debug_chat(self, app_id: UUID, req: DebugChatReq, account: Account) -> Generator:
        """会话调试"""
        app = self.get_app(app_id, account)

        draft_app_config = self.get_draft_app_config(app_id, account)

        debug_conversation = app.debug_conversation

        # 4. 新建一条消息
        message = self.create(
            Message,
            app_id=app_id,
            conversation_id=debug_conversation.id,
            created_by=account.id,
            query=req.query.data,
            image_urls=req.image_urls.data,
            status=MessageStatus.NORMAL
        )

        # 5 接入多LLM模型
        llm = self.language_model_service.load_language_model(draft_app_config.get("model_config", {}))

        # 6. 实例化tokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=debug_conversation,
            model_instance=llm
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=draft_app_config["dialog_round"]
        )
        # 7 草稿配置中的tools转换为langChain工具
        tools = self.app_config_service.get_langchain_tools_by_tools_config(draft_app_config["tools"], str(account.id))
        # 8 检测是否关联了知识库
        if draft_app_config["datasets"]:
            # 11.1 构建langchain知识库检索工具
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in draft_app_config["datasets"]],
                account_id=account.id,
                retrieval_source=RetrievalSource.APP,
                **draft_app_config["retrieval_config"]
            )
            tools.append(dataset_retrieval)

        # 9 关联工作流
        if draft_app_config["workflows"]:
            workflow_tools = self.app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow["id"] for workflow in draft_app_config["workflows"]]
            )
            tools.extend(workflow_tools)
        # 10 mcp工具集成
        mcps = []
        if draft_app_config["mcps"]:
            mcps = self.app_config_service.get_mcps_by_mcp_ids(
                [mcp["id"] for mcp in draft_app_config["mcps"]]
            )

        # 10 构建Agent智能体
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReactAgent
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.DEBUGGER,
                preset_prompt=draft_app_config["preset_prompt"],
                enable_long_term_memory=draft_app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=draft_app_config["review_config"],
                mcps=mcps
            )
        )

        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [llm.convert_to_human_message(req.query.data, req.image_urls.data)],
            "history": history,
            "long_term_memory": debug_conversation.summary
        }):
            # 15 提取thought以及answer
            event_id = str(agent_thought.id)
            # 17 将数据填充到agent_thought, 便于存储到数据库服务中
            if agent_thought.event != QueueEvent.PING:
                # 18 除了agent_message数据为叠加，其他均为覆盖
                if agent_thought.event == QueueEvent.AGENT_MESSAGE or agent_thought.event == QueueEvent.AGENT_THINK:
                    if event_id not in agent_thoughts:
                        # 19 初始化智能体消息事件
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 20. 叠加智能体消息
                        agent_thoughts[event_id] = agent_thoughts[event_id].model_copy(update={
                            "thought": agent_thoughts[event_id].thought + agent_thought.thought,
                            # 消息相关数据
                            "message": agent_thought.message,
                            "message_token_count": agent_thought.message_token_count,
                            "message_unit_price": agent_thought.message_unit_price,
                            "message_price_unit": agent_thought.message_price_unit,
                            # 答案相关数据
                            "answer": agent_thoughts[event_id].answer + agent_thought.answer,
                            "answer_token_count": agent_thought.answer_token_count,
                            "answer_unit_price": agent_thought.answer_unit_price,
                            "answer_price_unit": agent_thought.answer_price_unit,
                            # 推理统计
                            "total_token_count": agent_thought.total_token_count,
                            "total_price": agent_thought.total_price,
                            "latency": agent_thought.latency
                        })
                else:
                    # 21. 处理其也类型事件的消息
                    agent_thoughts[event_id] = agent_thought

            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "message", "answer",
                    "latency", "total_token_count", "total_price"
                }),
                "id": event_id,
                "task_id": str(agent_thought.task_id),
                "message_id": str(message.id),
                "conversation_id": str(debug_conversation.id)
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=app_id,
            app_config=draft_app_config,
            conversation_id=debug_conversation.id,
            message_id=message.id,
            agent_thoughts=[agent_thought for agent_thought in agent_thoughts.values()]
        )

    def stop_debug_chat(self, app_id: UUID, task_id: UUID, account: Account) -> None:
        self.get_app(app_id, account)

        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.DEBUGGER, account.id)

    def get_debug_conversation_message_with_page(self,
                                                 app_id: UUID,
                                                 req: GetDebugConversationMessagesWithPageReq,
                                                 account: Account) -> tuple[list[Message], Paginator]:
        """获取调试会话消息列表分页数据"""
        app = self.get_app(app_id, account)

        debug_conversation = app.debug_conversation

        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            created_at_datetime = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_datetime)

        messages = paginator.paginate(
            self.db.session.query(Message).filter(
                Message.conversation_id == debug_conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                *filters
            ).order_by(desc("created_at"))
        )

        return messages, paginator

    def get_published_config(self, app_id: UUID, account: Account) -> dict[str, Any]:
        app = self.get_app(app_id, account)

        return {
            "web_app": {
                "token": app.token_with_default,
                "ex_link_token": app.ex_link_token,
                "status": app.status
            }
        }

    def regenerate_web_app_token(self, app_id: UUID, account: Account) -> str:
        """生成webapp凭证标识"""
        app = self.get_app(app_id, account)

        if app.status != AppStatus.PUBLISHED:
            raise FailException("应用未发布，无法生成WebApp凭证标识")

        token = generate_random_string(16)
        self.update(app, token=token)

        return token

    def generate_token_with_ex_link(self, app_id: UUID, account: Account) -> dict[str, Any]:
        app = self.get_app(app_id, account)
        return {
            "web_app": {
                "token": app.ex_link_token_with_default,
                "status": app.status
            }
        }

    def cancel_published_with_ex_link(self, app_id: UUID, account: Account):
        app = self.get_app(app_id, account)
        self.update(app, ex_link_token=None)

    def _validate_draft_app_config(self, draft_app_config: dict[str, Any], account: Account) -> dict[str, Any]:
        """校验应用草稿配置信息，返回校验后的数据"""
        # .1 校验上传配置中的对应字符，至少拥有一个可以更新的配置
        acceptable_fields = [
            "model_config", "dialog_round", "preset_prompt",
            "tools", "workflows", "mcps", "datasets", "retrieval_config",
            "long_term_memory", "opening_statement", "opening_questions",
            "speech_to_text", "text_to_speech", "suggested_after_answer", "review_config"
        ]
        # 2. 判断传递的草稿配置是否可接受字段内
        if (
                not draft_app_config
                or not isinstance(draft_app_config, dict)
                or set(draft_app_config.keys()) - set(acceptable_fields)
        ):
            logging.error(f"草稿配置字段出错，请核实后重试 {draft_app_config}")
            raise ValidateErrorException("草稿配置字段出错，请核实后重试")
        # 3. 校验model_config字段，严格校验
        if "model_config" in draft_app_config:
            # 3.1 获取模型配置是否为字典
            model_config = draft_app_config["model_config"]
            if not isinstance(model_config, dict):
                raise ValidateErrorException("模型配置格式错误，请核实后重试")
            # 3.2 判断model_config键信息是否正确
            if set(model_config.keys()) != {"provider", "model", "parameters"}:
                raise ValidateErrorException("模型键配置格式错误，请核实后重试")

            # 3.3 判断模型提供者信息是否正确
            if not model_config["provider"] or not isinstance(model_config["provider"], str):
                raise ValidateErrorException("模型服务提供商类型必须为字符串")
            provider = self.language_model_manager.get_provider(model_config["provider"])
            if not provider:
                raise ValidateErrorException("该模型服务提供商不存在，请核实后重试")

            # 3.4 判断模型信息是否正确
            if not model_config["model"] or not isinstance(model_config["model"], str):
                raise ValidateErrorException("模型名字必须是否字符串")
            model_entity = provider.get_model_entity(model_config["model"])
            if not model_entity:
                raise ValidateErrorException("该服务提供商下不存在该模型，请核实后重试")

            # 3.5 判断传递的parameters是否正确，如果不正确则设置默认值，并剔除多余字段，补全未传递的字段
            parameters = {}
            for parameter in model_entity.parameters:
                # 3.6 从model_config中获取参数值，如果不存在则设置为默认值
                parameter_value = model_config["parameters"].get(parameter.name, parameter.default)

                # 3.7 判断参数是否必填
                if parameter.required:
                    # 3.8 参数必填，则值不允许为None，如果为None则设置默认值
                    if parameter_value is None:
                        parameter_value = parameter.default
                    else:
                        # 3.9 值非空则校验数据类型是否正确，不正确则设置默认值
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default
                else:
                    # 3.10 参数非必填，数据非空的情况下需要校验
                    if parameter_value is not None:
                        if get_value_type(parameter_value) != parameter.type.value:
                            parameter_value = parameter.default

                # 3.11 判断参数是否存在options，如果存在则数值必须在options中选择
                if parameter.options and parameter_value not in parameter.options:
                    parameter_value = parameter.default

                # 3.12 参数类型为int/float，如果存在min/max时候需要校验
                if parameter.type in [ModelParameterType.INT,
                                      ModelParameterType.FLOAT] and parameter_value is not None:
                    # 3.13 校验数值的min/max
                    if (
                            (parameter.min and parameter_value < parameter.min)
                            or (parameter.max and parameter_value > parameter.max)
                    ):
                        parameter_value = parameter.default

                parameters[parameter.name] = parameter_value

            # 3.13 覆盖Agent配置中的模型配置
            model_config["parameters"] = parameters
            draft_app_config["model_config"] = model_config

        # 4. 校验dialog_round字段
        if "dialog_round" in draft_app_config:
            dialog_round = draft_app_config["dialog_round"]
            if not isinstance(dialog_round, int) or not (0 <= dialog_round <= 100):
                raise ValidateErrorException("携带上下文轮数范围为0-100")

        # 5. 校验preset_prompt
        if "preset_prompt" in draft_app_config:
            preset_prompt = draft_app_config["preset_prompt"]
            if not isinstance(preset_prompt, str) or len(preset_prompt) > 2000:
                raise ValidateErrorException("人设与回复逻辑必须是字符串，长度在0-2000个字符")

        # 6. 校验tools字段
        if "tools" in draft_app_config:
            tools = draft_app_config["tools"]
            validate_tools = []

            # 6.1 tools类型必须为列表，空列表则代表代表不需要绑定绑定任何工具
            if not isinstance(tools, list):
                raise ValidateErrorException("工具列表必须是列表型数据")
            # 6.2 tools长度不能超过5
            if len(tools) > 5:
                raise ValidateErrorException("Agent绑定的工具数量不能超过5个")
            # 6.3 循环校验工具里的每一个参数
            for tool in tools:
                # 6.4 校验tool非空并且类型为字典
                if not tool or not isinstance(tool, dict):
                    raise ValidateErrorException("绑定插件工具参数出错")
                # 6.5 校验tool参数是不是type, provider_id, tool_id, params
                if set(tool.keys()) != {"type", "provider_id", "tool_id", "params"}:
                    raise ValidateErrorException("绑定插件工具参数出错")
                # 6.5 校验tool的type类型是否为builtin_tool或api_tool
                if tool["type"] not in ["builtin_tool", "api_tool"]:
                    raise ValidateErrorException("绑定插件工具参数出错")
                # 6.7 校验provider_id和tool_id
                if (
                        not tool["provider_id"]
                        or not tool["tool_id"]
                        or not isinstance(tool["provider_id"], str)
                        or not isinstance(tool["tool_id"], str)
                ):
                    raise ValidateErrorException("插件提供者或者插件标识参数出错")
                # 6.8 校验params参数，类型为字典
                if not isinstance(tool["params"], dict):
                    raise ValidateErrorException("插件自定义参数格式错误")
                # 6.9 校验对应的工具是否存在，而且需要划分成builtin_tool和api_tool
                if tool["type"] == "builtin_tool":
                    builtin_tool = self.builtin_provider_manager.get_tool(tool["provider_id"], tool["tool_id"])
                    if not builtin_tool:
                        continue
                else:
                    api_tool = self.db.session.query(ApiTool).filter(
                        ApiTool.provider_id == tool["provider_id"],
                        ApiTool.name == tool["tool_id"],
                        ApiTool.account_id == account.id
                    ).one_or_none()
                    if not api_tool:
                        continue

                validate_tools.append(tool)

            # 6.10 校验绑定的工具是否重复
            check_tools = [f"{tool['provider_id']}_{tool['tool_id']}" for tool in validate_tools]
            if len(set(check_tools)) != len(validate_tools):
                raise ValidateErrorException("绑定插件存在重复")

            # 6.11 重新赋值工具
            draft_app_config["tools"] = validate_tools

        # 7. 校验workflows 提取已发布+权限正确的工作流列表进行绑定（更新阶段不验证工作流是否可以正常运行）
        if "workflows" in draft_app_config:
            workflows = draft_app_config["workflows"]

            if not isinstance(workflows, list):
                raise ValidateErrorException("绑定工作流列表参数格式错误")

            if len(workflows) > 5:
                raise ValidateErrorException("Agent绑定的工作流数据不能超过5个")

            for workflow_id in workflows:
                try:
                    UUID(workflow_id)
                except Exception as _:
                    raise ValidateErrorException("工作流参数必须是UUID")

            if len(set(workflows)) != len(workflows):
                raise ValidateErrorException("绑定工作流存在重复")

            workflow_records = self.db.session.query(Workflow).filter(
                Workflow.id.in_(workflows),
                Workflow.account_id == account.id,
                Workflow.status == WorkflowStatus.PUBLISHED
            ).all()
            workflow_sets = set([str(workflow_record.id) for workflow_record in workflow_records])
            draft_app_config["workflows"] = [workflow_id for workflow_id in workflows if workflow_id in workflow_sets]

        # 8. 校验datasets知识库列表
        if "datasets" in draft_app_config:
            datasets = draft_app_config["datasets"]
            # 8.1 判断datasets类型是否为列表
            if not isinstance(datasets, list):
                raise ValidateErrorException("绑定知识库列表参数格式出错")
            # 8.2 判断关联的知识库列表是否超过5
            if len(datasets) > 5:
                raise ValidateErrorException("绑定知识库列表数量不能超过5个")
            # 8.3 循环校验知识库的每个参数
            for dataset_id in datasets:
                try:
                    UUID(dataset_id)
                except Exception as e:
                    raise ValidateErrorException("知识库列表参数必须是UUID")
            # 8.4 判断是否传递了重复的知识库
            if len(set(datasets)) != len(datasets):
                raise ValidateErrorException("绑定知识库存在重复")
            # 8.5 校验绑定的知识库权限，剔除不属于当前账号的知识库
            dataset_records = self.db.session.query(Dataset).filter(
                Dataset.id.in_(datasets),
                Dataset.account_id == account.id
            ).all()
            dataset_sets = set([str(dataset_record.id) for dataset_record in dataset_records])
            draft_app_config["datasets"] = [dataset_id for dataset_id in datasets if dataset_id in dataset_sets]

        # 9. 校验retrieval_config
        if "retrieval_config" in draft_app_config:
            retrieval_config = draft_app_config["retrieval_config"]
            # 9.1 判断检索配置非空且类型为字典
            if not retrieval_config or not isinstance(retrieval_config, dict):
                raise ValidateErrorException("检索配置格式错误")

            # 9.2 校验检索配置的字段类型
            if set(retrieval_config.keys()) != {"retrieval_strategy", "k", "score"}:
                raise ValidateErrorException("检索配置格式错误")

            # 9.3 校验检索策略是否正确
            if retrieval_config["retrieval_strategy"] not in ["semantic", "full_text", "hybrid"]:
                raise ValidateErrorException("检测策略格式错误")

            # 9.4 校验最大召回数量
            if not isinstance(retrieval_config["k"], int) or not (0 <= retrieval_config["k"] <= 10):
                raise ValidateErrorException("最大召回数量范围0~10")
            # 9.5 校验 score
            if not isinstance(retrieval_config["score"], float) or not (0 <= retrieval_config["score"] < 1):
                raise ValidateErrorException("得分匹配范围0~1")
        # 10 校验long_term_memory长期记录配置
        if "long_term_memory" in draft_app_config:
            long_term_memory = draft_app_config["long_term_memory"]

            # 10.1 校验长期记忆格式
            if not long_term_memory or not isinstance(long_term_memory, dict):
                raise ValidateErrorException("长期记忆设置格式错误")
            # 10.2 校验长期记忆属性
            if (set(long_term_memory.keys()) != {"enable"}
                    or not isinstance(long_term_memory["enable"], bool)
            ):
                raise ValidateErrorException("长期记忆设置格式错误")
        # 11 校验opening_statement
        if "opening_statement" in draft_app_config:
            opening_statement = draft_app_config["opening_statement"]
            # 11.1 校验对话开场白类型以及长度
            if not isinstance(opening_statement, str) or len(opening_statement) > 2000:
                raise ValidateErrorException("对话开场白的长度范围0~2000")
        # 12 校验opening_questions
        if "opening_questions" in draft_app_config:
            opening_questions = draft_app_config["opening_questions"]
            # 12.1 校验是否为列表，并且长度不超过3
            if not isinstance(opening_questions, list) or len(opening_questions) > 3:
                raise ValidateErrorException("开场建议问题不能超过3个")
            # 12.2 开场建议问题每个元素都是一个字符串
            for opening_question in opening_questions:
                if not isinstance(opening_question, str):
                    raise ValidateErrorException("开场建议问题必须是字符串")
        # 13 校验speech_to_text
        if "speech_to_text" in draft_app_config:
            speech_to_text = draft_app_config["speech_to_text"]
            # 13.1 校验长期记忆格式
            if not speech_to_text or not isinstance(speech_to_text, dict):
                raise ValidateErrorException("语言转文本设置格式错误")
            # 13.2 校验长期记忆属性
            if (set(speech_to_text.keys()) != {"enable"}
                    or not isinstance(speech_to_text["enable"], bool)
            ):
                raise ValidateErrorException("语言转文本设置格式错误")
        # 14 校验text_to_speech
        if "text_to_speech" in draft_app_config:
            text_to_speech = draft_app_config["text_to_speech"]
            # 13.1 校验长期记忆格式
            if not text_to_speech or not isinstance(text_to_speech, dict):
                raise ValidateErrorException("文本转语音设置格式错误")
            # 13.2 校验长期记忆属性
            if (set(text_to_speech.keys()) != {"enable", "voice", "auto_play"}
                    or not isinstance(text_to_speech["enable"], bool)
                    # todo: 音色需要多模态Agent的支持
                    or text_to_speech["voice"] not in ALLOWED_AUDIO_VOICES
                    or not isinstance(text_to_speech["auto_play"], bool)
            ):
                raise ValidateErrorException("文本转语音设置格式错误")

        # 15.校验回答后生成建议问题
        if "suggested_after_answer" in draft_app_config:
            suggested_after_answer = draft_app_config["suggested_after_answer"]

            # 10.1 校验回答后建议问题格式
            if not suggested_after_answer or not isinstance(suggested_after_answer, dict):
                raise ValidateErrorException("回答后建议问题设置格式错误")
            # 10.2 校验回答后建议问题格式
            if (
                    set(suggested_after_answer.keys()) != {"enable"}
                    or not isinstance(suggested_after_answer["enable"], bool)
            ):
                raise ValidateErrorException("回答后建议问题设置格式错误")

        # 16 校验review_config
        if "review_config" in draft_app_config:
            review_config = draft_app_config["review_config"]
            # 15.1 校验字段格式、非空
            if not review_config or not isinstance(review_config, dict):
                raise ValidateErrorException("审核配置格式错误")
            # 15.2 校验字段信息
            if set(review_config.keys()) != {"enable", "keywords", "inputs_config", "outputs_config"}:
                raise ValidateErrorException("审核配置格式错误")
            # 15.3 校验enable
            if not isinstance(review_config["enable"], bool):
                raise ValidateErrorException("review.enable格式错误")
            # 15.4 校验keywords
            if (not isinstance(review_config["keywords"], list)
                    or (review_config["enable"] and len(review_config["keywords"]) == 0)
                    or len(review_config["keywords"]) > 100
            ):
                raise ValidateErrorException("review.keywords非空并且不能超100个关键词")
            for keyword in review_config["keywords"]:
                if not isinstance(keyword, str):
                    raise ValidateErrorException("review.keywords敏感词必须是字符串")
            # 15.5 校验inputs_config
            if (
                    not review_config["inputs_config"]
                    or not isinstance(review_config["inputs_config"], dict)
                    or set(review_config["inputs_config"].keys()) != {"enable", "preset_response"}
                    or not isinstance(review_config["inputs_config"]["enable"], bool)
                    or not isinstance(review_config["inputs_config"]["preset_response"], str)
            ):
                raise ValidateErrorException("review.inputs_config必须是一个字典")
            # 15.6 校验outputs_config
            if (
                    not review_config["outputs_config"]
                    or not isinstance(review_config["outputs_config"], dict)
                    or set(review_config["outputs_config"].keys()) != {"enable"}
                    or not isinstance(review_config["outputs_config"]["enable"], bool)
            ):
                raise ValidateErrorException("review.outputs_config必须是一个字典")
            # 15.7 审核模块开启后，必须确保inputs_config、outputs_config至少有一个是开启状态
            if review_config["enable"]:
                if (
                        review_config["inputs_config"]["enable"] is False
                        and review_config["outputs_config"]["enable"] is False
                ):
                    raise ValidateErrorException("输入审核和转出审核至少需要开启一个")
                if (
                        review_config["inputs_config"]["enable"]
                        and review_config["inputs_config"]["preset_response"].strip() == ""
                ):
                    raise ValidateErrorException("输入审核预设响应不能为空")

        # 17. 校验Mcp tools配置（更新阶段不验证Mcp tool是否可以正常运行）
        if "mcps" in draft_app_config:
            mcps = draft_app_config["mcps"]
            if not isinstance(mcps, list):
                raise ValidateErrorException("绑定Mcp列表参数格式错误")

            if len(mcps) > 5:
                raise ValidateErrorException("Agent绑定的Mcp数据不能超过5个")

            for mcp_id in mcps:
                try:
                    UUID(mcp_id)
                except Exception as _:
                    raise ValidateErrorException("Mcp参数必须是UUID")

            if len(set(mcps)) != len(mcps):
                raise ValidateErrorException("绑定Mcp存在重复")

            mcp_records = self.db.session.query(McpTool).filter(
                McpTool.id.in_(mcps),
                McpTool.account_id == account.id
            ).all()
            mcp_sets = set([str(mcp_record.id) for mcp_record in mcp_records])
            draft_app_config["mcps"] = [mcp_id for mcp_id in mcps if
                                        mcp_id in mcp_sets]
        return draft_app_config
