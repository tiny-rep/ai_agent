import json
from dataclasses import dataclass
from datetime import datetime
from typing import Generator, Any
from uuid import UUID

from flask import current_app
from injector import inject
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import desc
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func

from internal.core.agent.agents import FunctionCallAgent, ReactAgent
from internal.core.agent.entities.agnet_entity import AgentConfig
from internal.core.agent.entities.queue_entity import QueueEvent
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.memory import TokenBufferMemory
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import InvokeFrom, MessageStatus
from internal.entity.dataset_entity import RetrievalSource
from internal.entity.openapi_entiry import OPENAPI_STRUCT_OUTPUT_TEMPLATE_NAME
from internal.exception import NotFoundException, ForbiddenException
from internal.model import Account, EndUser, Conversation, Message, App
from internal.schema.conversation_schema import GetConversationMessagesWithPageReq
from internal.schema.openapi_schema import OpenAPIChatReq
from pkg.paginator import Paginator
from pkg.reponse import Response
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService
from .app_service import AppService
from .base_service import BaseService
from .conversation_service import ConversationService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService
from ..lib.helper import convert_model_to_dict
from ..lib.json_pydantic import json_2_model
from ..schema.app_schema import GetAppsWithPageReq


@inject
@dataclass
class OpenapiService(BaseService):
    """OpenAPI开放服务"""
    db: SQLAlchemy
    app_service: AppService
    retrieval_service: RetrievalService
    app_config_service: AppConfigService
    conversation_service: ConversationService
    language_model_service: LanguageModelService

    def ex_link_chat(self, req: OpenAPIChatReq, account: Account):
        # 1. 判断当前应用是否属于当前账号
        app = self.app_service.get_app(req.app_id.data, account)

        if req.end_user_id.data:
            end_user = self.get(EndUser, req.end_user_id.data)
            if not end_user:
                self.create(
                    EndUser,
                    **{"id": req.end_user_id.data, "tenant_id": account.id, "app_id": app.id}
                )
        else:
            raise NotFoundException("终端用户Id不能为空")

        return self.chat(req, account)

    def chat(self, req: OpenAPIChatReq, account: Account):

        """根据账号信息发起聊天对话，返回数据为块行后或生成器"""
        # 1. 判断当前应用是否属于当前账号
        app = self.app_service.get_app(req.app_id.data, account)

        # 2. 判断此应用是否已发布
        if not app or app.status != AppStatus.PUBLISHED:
            raise NotFoundException("应用不存在或者末发布，请核实后重试")

        # 3. 判断是否传递了终端用户id，如果传递了则检测终端用户关联的应用
        if req.end_user_id.data:
            end_user = self.get(EndUser, req.end_user_id.data)
            if not end_user or end_user.app_id != app.id:
                raise ForbiddenException("当前账号不存在或者不属于该应用，请核实后重试")
        else:
            # 4. 终端用户不存在，则创建一个
            end_user = self.create(
                EndUser,
                **{"tenant_id": account.id, "app_id": app.id}
            )
        # 5. 检测是否传递了会话id，需要检测会话的归属信息
        if req.conversation_id.data:
            conversation = self.get(Conversation, req.conversation_id.data)
            if (
                    not conversation
                    or conversation.app_id != app.id
                    or conversation.invoke_from != InvokeFrom.SERVICE_API
                    or conversation.created_by != end_user.id
            ):
                raise ForbiddenException("该会话不存在，或者不属于该应用/终端用户/调用方式")
        else:
            # 6. 如果不存在则创建新的会话信息
            conversation = self.create(Conversation,
                                       **{
                                           "app_id": app.id,
                                           "name": "New Conversation",
                                           "invoke_from": InvokeFrom.SERVICE_API,
                                           "created_by": end_user.id
                                       })
        # 7 获取校验后的运行时配置
        app_config = self.app_config_service.get_app_config(app)

        # 8 新建一条消息
        message = self.create(Message, **{
            "app_id": app.id,
            "conversation_id": conversation.id,
            "invoke_from": InvokeFrom.SERVICE_API,
            "created_by": end_user.id,
            "query": req.query.data,
            "image_urls": req.image_urls.data,
            "status": MessageStatus.NORMAL
        })

        # 9. LLM多模态接入
        llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

        # 10 创建提取短期记忆
        token_buffer_memory = TokenBufferMemory(
            db=self.db,
            conversation=conversation,
            model_instance=llm
        )
        history = token_buffer_memory.get_history_prompt_messages(
            message_limit=app_config["dialog_round"]
        )

        # 11. 将配置中的tools转成tools
        tools = self.app_config_service.get_langchain_tools_by_tools_config(app_config["tools"], str(account.id))

        # 12. 检测是否关联知识库
        if app_config["datasets"]:
            # 13 构建langchain知识库检测工具
            datasets_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                flask_app=current_app._get_current_object(),
                dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                account_id=account.id,
                retrieval_source=RetrievalSource.APP,
                **app_config["retrieval_config"]
            )
            tools.append(datasets_retrieval)

        # 14.检测是否关联工作流，如果关联了工作流则将工作流构建成工具添加到tools中
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

        # 14. 构建 agent 智能体
        agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReactAgent
        agent = agent_class(
            llm=llm,
            agent_config=AgentConfig(
                user_id=account.id,
                invoke_from=InvokeFrom.SERVICE_API,
                preset_prompt=app_config["preset_prompt"],
                enable_long_term_memory=app_config["long_term_memory"]["enable"],
                tools=tools,
                review_config=app_config["review_config"],
                mcps=mcps
            )
        )

        # 15. 定义智能体状态基础信息
        agent_state = {
            "messages": [llm.convert_to_human_message(req.query.data, req.image_urls.data)],
            "history": history,
            "long_term_memory": conversation.summary
        }

        if req.stream.data is True:
            """流式输出"""
            agent_thoughts_dict = {}

            def handle_stream() -> Generator:
                for agent_thought in agent.stream(agent_state):
                    event_id = str(agent_thought.id)
                    if agent_thought.event != QueueEvent.PING:
                        # 3. 单独处理agent_message事件，此事件为叠加
                        if agent_thought.event == QueueEvent.AGENT_MESSAGE or agent_thought.event == QueueEvent.AGENT_THINK:
                            # 4. 检测是否已存储事件
                            if event_id not in agent_thoughts_dict:
                                # 5. 初始化事件
                                agent_thoughts_dict[event_id] = agent_thought
                            else:
                                # 6. 叠加消息事件
                                agent_thoughts_dict[event_id] = agent_thoughts_dict[event_id].model_copy(
                                    update={
                                        "thought": agent_thoughts_dict[event_id].thought + agent_thought.thought,
                                        "answer": agent_thoughts_dict[event_id].answer + agent_thought.answer,
                                        "latency": agent_thought.latency
                                    })
                        else:
                            agent_thoughts_dict[event_id] = agent_thought

                    data = {
                        **agent_thought.model_dump(include={
                            "event", "thought", "observation", "tool", "tool_input", "message", "answer", "latency"
                        }),
                        "id": event_id,
                        "end_user_id": str(end_user.id),
                        "task_id": str(agent_thought.task_id),
                        "message_id": str(message.id),
                        "conversation_id": str(conversation.id)
                    }
                    yield f"event: {agent_thought.event}\ndata:{json.dumps(data)}\n\n"

                self.conversation_service.save_agent_thoughts(
                    account_id=account.id,
                    app_id=app.id,
                    app_config=app_config,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    agent_thoughts=[agent_thought for agent_thought in agent_thoughts_dict.values()]
                )

            return handle_stream()

        # 16. 生成数据
        agent_result = agent.invoke(agent_state)

        struct_result = ""
        if req.struct_output.data:
            struct_obj = json.loads(req.struct_output.data)
            struct_result = self.convert_message_struct(agent_result.answer, struct_obj)

        self.conversation_service.save_agent_thoughts(
            account_id=account.id,
            app_id=app.id,
            app_config=app_config,
            conversation_id=conversation.id,
            message_id=message.id,
            agent_thoughts=agent_result.agent_thoughts
        )

        return Response(data={
            "id": str(message.id),
            "end_user_id": str(end_user.id),
            "conversation_id": str(conversation.id),
            "query": req.query.data,
            "image_urls": req.image_urls.data,
            "answer": agent_result.answer,
            "total_token_count": 0,
            "latency": agent_result.latency,
            "struct_result": struct_result,
            "agent_thoughts": [
                {
                    "id": str(agent_thought.id),
                    "event": agent_thought.event,
                    "thought": agent_thought.thought,
                    "observation": agent_thought.observation,
                    "tool": agent_thought.tool,
                    "tool_input": agent_thought.tool_input,
                    "latency": agent_thought.latency,
                    "created_at": 0
                } for agent_thought in agent_result.agent_thoughts
            ]
        })

    def get_conversation(self, conversation_id: UUID, end_user_id: UUID, account: Account) -> Conversation:
        """获取指定会话信息"""
        conversation = self.get(Conversation, conversation_id)
        if (
                not conversation
                or conversation.created_by != end_user_id
                or conversation.is_deleted
        ):
            raise NotFoundException("该会话不存在或者被删除，请核实后重试")

        return conversation

    def get_message(self, message_id: UUID, end_user_id: UUID, account: Account) -> Message:
        message = self.get(Message, message_id)
        if (
                not message
                or message.created_by != end_user_id
                or message.is_deleted
        ):
            raise NotFoundException("该消息不存在或者被删除，请核实后重试")
        return message

    def get_conversation_messages_with_page(self,
                                            conversation_id: UUID,
                                            end_user_id: UUID,
                                            req: GetConversationMessagesWithPageReq,
                                            account: Account):
        """获取指定会话的消息列表"""
        conversation = self.get_conversation(conversation_id, end_user_id, account)
        paginator = Paginator(db=self.db, req=req)
        filters = []
        if req.created_at.data:
            created_at_time = datetime.fromtimestamp(req.created_at.data)
            filters.append(Message.created_at <= created_at_time)

        messages = paginator.paginate(
            self.db.session.query(Message).options(joinedload(Message.agent_thoughts)).filter(
                Message.conversation_id == conversation.id,
                Message.status.in_([MessageStatus.STOP, MessageStatus.NORMAL]),
                Message.answer != "",
                ~Message.is_deleted,
                *filters
            ).order_by(desc("created_at"))
        )

        return messages, paginator

    def init_new_conversation(self,
                              conversation_id: UUID,
                              end_user_id: UUID,
                              app_id: UUID,
                              account: Account
                              ):
        """初始化一条空的新会话"""
        # 1. 初始化end_user
        end_user = self.get(EndUser, end_user_id)
        if not end_user:
            end_user = self.create(
                EndUser,
                **{"id": end_user_id, "tenant_id": account.id, "app_id": app_id}
            )
        # 2. 初始化会话
        conversation = self.get(Conversation, conversation_id)
        if not conversation:
            self.create(Conversation,
                        **{
                            "id": conversation_id,
                            "app_id": app_id,
                            "name": "New Conversation Auto",
                            "invoke_from": InvokeFrom.SERVICE_API,
                            "created_by": end_user.id
                        })

    def delete_conversation(self, conversation_id: UUID, end_user_id: UUID, account: Account) -> Conversation:
        conversation = self.get_conversation(conversation_id, end_user_id, account)
        self.update(conversation, is_deleted=True)
        return conversation

    def delete_message(self, conversation_id: UUID, end_user_id: UUID, message_id: UUID, account: Account) -> Message:
        conversation = self.get_conversation(conversation_id, end_user_id, account)

        message = self.get_message(message_id, end_user_id, account)

        if conversation.id != message.conversation_id:
            raise NotFoundException("该会话下不存在该消息，请核实后重试")

        self.update(message, is_deleted=True)

        return message

    def update_conversation(self, conversation_id: UUID, end_user_id: UUID, account: Account, **kwargs) -> Conversation:
        conversation = self.get_conversation(conversation_id, end_user_id, account)

        self.update(conversation, **kwargs)

        return conversation

    def generate_suggested_questions_from_message_id_in_ex_link(self,
                                                                message_id: UUID,
                                                                end_user_id: UUID,
                                                                account: Account):
        """生成建议问题列表"""
        message = self.get(Message, message_id)

        if not message or message.created_by != end_user_id:
            raise ForbiddenException("该条消息不存在或者无权限")

        histories = f"Human:{message.query}\nAI:{message.answer}"

        return self.conversation_service.generate_suggested_questions(histories)

    def get_apps_with_page_ex_link(self, req: GetAppsWithPageReq) -> tuple[list[App], Paginator]:
        paginator = Paginator(db=self.db, req=req)

        filters = [App.ex_link_token.isnot(None), App.ex_link_token != '']
        if req.search_word.data:
            filters.append(App.name.ilike(f"%{req.search_word.data}%"))
        apps = paginator.paginate(
            self.db.session.query(App).filter(*filters).order_by(desc("created_at"))
        )
        return apps, paginator

    def get_hot_apps_with_ex_link(self) -> list[App]:

        hot_apps = self.db.session.query(
            EndUser.app_id,
            func.count(EndUser.id).label("count")
        ).group_by(
            EndUser.app_id
        ).order_by(
            func.count(EndUser.id).desc()
        ).limit(4).all()
        hot_app_ids = [rec.app_id for rec in hot_apps]

        if hot_app_ids is None or len(hot_app_ids) <= 0:
            return []

        filters = [App.ex_link_token.isnot(None), App.ex_link_token != '']
        filters.append(App.id.in_(hot_app_ids))
        query = self.db.session.query(App).filter(*filters).order_by(
            desc("created_at")
        )
        # print(query.statement.compile())
        apps = query.all()

        return apps

    def convert_message_struct(self, ai_message: str, req: Any):
        """对数据进行结构化处理"""
        model = json_2_model("MessageToStruct", req.get("description"), req.get("schema"))

        prompt = ChatPromptTemplate.from_messages([
            ("system", OPENAPI_STRUCT_OUTPUT_TEMPLATE_NAME),
            ("human", "{data}")
        ])

        llm = self.language_model_service.load_default_language_model_with_config(temperature=0.2)
        llm_struct = llm.with_structured_output(model)

        chain = prompt | llm_struct

        result = chain.invoke({"data": ai_message})
        result_json = convert_model_to_dict(result)
        return result_json
