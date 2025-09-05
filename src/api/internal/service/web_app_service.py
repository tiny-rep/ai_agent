import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Generator, Any, Dict
from uuid import UUID

from flask import current_app
from injector import inject
from sqlalchemy import desc

from internal.core.agent.agents import FunctionCallAgent, ReactAgent, AgentQueueManager
from internal.core.agent.entities.agnet_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.memory import TokenBufferMemory
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.exception import NotFoundException, ForbiddenException
from internal.model import App, Account, Conversation, Message
from internal.schema.web_app_schema import WebAppChatReq
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService
from .base_service import BaseService
from .conversation_service import ConversationService
from .jwt_service import JwtService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService


@inject
@dataclass
class WebAppService(BaseService):
    """WebApp服务"""
    db: SQLAlchemy
    app_config_service: AppConfigService
    retrieval_service: RetrievalService
    conversation_service: ConversationService
    language_model_service: LanguageModelService
    jwt_service: JwtService

    def get_web_app(self, token: str) -> App:
        app = self.db.session.query(App).filter(
            App.token == token
        ).one_or_none()
        if not app or app.status != AppStatus.PUBLISHED:
            raise NotFoundException("该WebAPP不存在或者未发布，请核实后重试")
        return app

    def get_web_app_info(self, token: str) -> Dict[str, Any]:
        app = self.get_web_app(token)
        return self._get_web_app_info(app)

    def web_app_chat(self, token: str, req: WebAppChatReq, account: Account) -> Generator:
        app = self.get_web_app(token)

        # 2 检测是否传递了会话id
        if req.conversation_id.data:
            conversation = self.get(Conversation, req.conversation_id.data)
            if (
                    not conversation
                    or conversation.app_id != app.id
                    or conversation.invoke_from != InvokeFrom.WEB_APP
                    or conversation.created_by != account.id
                    or conversation.is_deleted is True
            ):
                raise ForbiddenException("该会话不存在，或者不属于当前用户/应用/调用方式")
        else:
            conversation = self.create(Conversation, **{
                "app_id": app.id,
                "name": "New Conversation",
                "invoke_from": InvokeFrom.WEB_APP,
                "created_by": account.id
            })

        # 4. 获取校验后的运行配置
        app_config = self.app_config_service.get_app_config(app)

        # 5.新建一条消息记录
        message = self.create(
            Message,
            app_id=app.id,
            conversation_id=conversation.id,
            invoke_from=InvokeFrom.WEB_APP,
            created_by=account.id,
            query=req.query.data,
            image_urls=req.image_urls.data,
            status=MessageStatus.NORMAL,
        )

        # 6.从语言模型管理器中加载大语言模型
        llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        # 7.实例化TokenBufferMemory用于提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm,
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"],
        )

        # 8.将草稿配置中的tools转换成LangChain工具
        tools = self.app_config_service.get_langchain_tools_by_tools_config(app_config["tools"], str(account.id))

        # 9.检测是否关联了知识库
        if app_config["datasets"]:
            # 10.构建LangChain知识库检索工具
            dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                account_id=account.id,
                retrieval_source=RetrievalSource.APP,
                **app_config["retrieval_config"],
            )
            tools.append(dataset_retrieval)

        # 11.检测是否关联工作流，如果关联了工作流则将工作流构建成工具添加到tools中
        if app_config["workflows"]:
            workflow_tools = self.app_config_service.get_langchain_tools_by_workflow_ids(
                [workflow["id"] for workflow in app_config["workflows"]]
            )
            tools.extend(workflow_tools)

        # 11 mcp工具集成
        mcps = []
        if app_config["mcps"]:
            mcps = self.app_config_service.get_mcps_by_mcp_ids(
                [mcp["id"] for mcp in app_config["mcps"]]
            )

        # 12.根据LLM是否支持tool_call决定使用不同的Agent
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReactAgent
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.WEB_APP,
                preset_prompt=app_config["preset_prompt"],
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=app_config["review_config"],
                mcps=mcps
            ),
        )

        # 13.定义字典存储推理过程，并调用智能体获取消息
        agent_thoughts = {}
        for agent_thought in agent.stream({
            "messages": [llm.convert_to_human_message(req.query.data, req.image_urls.data)],
            "history": history,
            "long_term_memory": conversation.summary,
        }):
            # 14.提取thought以及answer
            event_id = str(agent_thought.id)

            # 15.将数据填充到agent_thought，便于存储到数据库服务中
            if agent_thought.event != QueueEvent.PING:
                # 16.除了agent_message数据为叠加，其他均为覆盖
                if agent_thought.event == QueueEvent.AGENT_MESSAGE or agent_thought.event == QueueEvent.AGENT_THINK:
                    if event_id not in agent_thoughts:
                        # 17.初始化智能体消息事件
                        agent_thoughts[event_id] = agent_thought
                    else:
                        # 18.叠加智能体消息
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
                            # Agent推理统计相关
                            "total_token_count": agent_thought.total_token_count,
                            "total_price": agent_thought.total_price,
                            "latency": agent_thought.latency,
                        })
                else:
                    # 19.处理其他类型事件的消息
                    agent_thoughts[event_id] = agent_thought
            data = {
                **agent_thought.model_dump(include={
                    "event", "thought", "observation", "tool", "tool_input", "answer",
                    "total_token_count", "total_price", "latency",
                }),
                "id": event_id,
                "conversation_id": str(conversation.id),
                "message_id": str(message.id),
                "task_id": str(agent_thought.task_id),
            }
            yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

        # 20.将消息以及推理过程添加到数据库
        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=app.id,
            app_config=app_config,
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=[agent_thought for agent_thought in agent_thoughts.values()]
        )

    def stop_web_app_chat(self, token: str, task_id: UUID, account: Account):
        self.get_web_app(token)

        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.WEB_APP, account.id)

    def get_conversations(self, token: str, is_pinned: bool, account: Account) -> list[Conversation]:
        app = self.get_web_app(token)

        conversations = self.db.session.query(Conversation).filter(
            Conversation.app_id == app.id,
            Conversation.created_by == account.id,
            Conversation.invoke_from == InvokeFrom.WEB_APP,
            Conversation.is_pinned == is_pinned,
            ~Conversation.is_deleted
        ).order_by(desc("created_at")).all()

        return conversations

    def generate_access_token_with_ex_link(self, ex_link_token: str) -> Dict[str, Any]:
        """根据用户的外链 生成 授权Token"""
        app = self._get_web_app_with_ex_link(ex_link_token)

        expire_at = ((datetime.now() + timedelta(days=360)).timestamp())
        payload = {
            "sub": str(app.account_id),
            "iss": "llmops-exLink",
            "ex_link_token": ex_link_token,
            "exp": expire_at
        }
        account_token = self.jwt_service.generate_token(payload)

        return {
            "expire_at": expire_at,
            "access_token": account_token
        }

    def get_conversations_with_end_user_id(self, ex_link_token: str, is_pinned: bool, end_user_id: UUID) -> list[
        Conversation]:
        app = self._get_web_app_with_ex_link(ex_link_token)

        conversations = self.db.session.query(Conversation).filter(
            Conversation.app_id == app.id,
            Conversation.created_by == end_user_id,
            Conversation.invoke_from == InvokeFrom.SERVICE_API,
            Conversation.is_pinned == is_pinned,
            ~Conversation.is_deleted
        ).order_by(desc("created_at")).all()

        return conversations

    def get_web_app_info_with_ex_link(self, ex_link_token: str) -> dict[str, Any]:
        app = self._get_web_app_with_ex_link(ex_link_token)
        return self._get_web_app_info(app)

    def stop_web_app_chat_ex_link(self, ex_link_token: str, task_id: UUID, account: Account):
        self._get_web_app_with_ex_link(ex_link_token)

        AgentQueueManager.set_stop_flag(task_id, InvokeFrom.SERVICE_API, account.id)

    def _get_web_app_with_ex_link(self, ex_link_token: str) -> App:
        app = self.db.session.query(App).filter(
            App.ex_link_token is not None and
            App.ex_link_token == ex_link_token
        ).one_or_none()
        if not app or app.status != AppStatus.PUBLISHED:
            raise NotFoundException("该WebAPP不存在或者不允许外链访问，请核实后重试")
        return app

    def _get_web_app_info(self, app: App):
        app_config = self.app_config_service.get_app_config(app)
        llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        return {
            "id": str(app.id),
            "icon": app.icon,
            "name": app.name,
            "description": app.description,
            "app_config": {
                "opening_statement": app_config.get("opening_statement"),
                "opening_questions": app_config.get("opening_questions"),
                "suggested_after_answer": app_config.get("suggested_after_answer"),
                "features": llm.features,
                "text_to_speech": app_config.get("text_to_speech"),
                "speech_to_text": app_config.get("speech_to_text")
            }
        }
