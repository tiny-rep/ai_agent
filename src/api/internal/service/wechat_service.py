from dataclasses import dataclass
from threading import Thread
from typing import Any
from uuid import UUID

from flask import request, Flask, current_app
from injector import inject
from sqlalchemy import desc
from wechatpy import parse_message
from wechatpy.exceptions import InvalidSignatureException
from wechatpy.replies import TextReply
from wechatpy.utils import check_signature

from internal.core.agent.agents import FunctionCallAgent, ReactAgent
from internal.core.agent.entities.agnet_entity import AgentConfig
from internal.core.language_model.entities.model_entity import ModelFeature
from internal.core.memory import TokenBufferMemory
from internal.entity.app_entity import AppStatus
from internal.entity.conversation_entity import MessageStatus, InvokeFrom
from internal.entity.dataset_entity import RetrievalSource
from internal.entity.platform_entity import WechatConfigStatus
from internal.exception import FailException
from internal.model import App, WechatEndUser, EndUser, WechatMessage, Message, Conversation
from pkg.sqlalchemy import SQLAlchemy
from .app_config_service import AppConfigService
from .base_service import BaseService
from .conversation_service import ConversationService
from .language_model_service import LanguageModelService
from .retrieval_service import RetrievalService


@inject
@dataclass
class WechatService(BaseService):
    """wechat公众号服务"""
    db: SQLAlchemy
    retrieval_service: RetrievalService
    app_config_service: AppConfigService
    conversation_service: ConversationService
    language_model_service: LanguageModelService

    def wechat(self, app_id: UUID):
        app: App = self.get(App, app_id)
        msg = parse_message(request.data)

        if not app or app.status != AppStatus.PUBLISHED:
            if request.method == "GET":
                raise FailException("该应用未发布或不存在，无法使用，请核实后重试")
            else:
                reply = TextReply(content="该应用未发布或不存在，无法使用，请核实后重试", message=msg)
                return reply.render()

        # 3. 获取应用的WeChat的配置
        wechat_config = app.wechat_config
        if wechat_config.status != WechatConfigStatus.CONFIGURED:
            if request.method == "GET":
                raise FailException("该应用未发布到微信公众号，无法使用，请核实后重试")
            else:
                reply = TextReply(content="该应用未发布到微信公众号，无法使用，请核实后重试", message=msg)
                return reply.render()

        if request.method == "GET":
            # 签名校验
            signature = request.args.get("signature")
            timestamp = request.args.get("timestamp")
            nonce = request.args.get("nonce")
            echostr = request.args.get("echostr")
            try:
                check_signature(wechat_config.wechat_token, signature, timestamp, nonce)
                return echostr
            except InvalidSignatureException:
                raise FailException("微信公众号服务器配置接入失败")
        else:
            # 7. 校验发送的消息类型，仅支持传递文本消息
            if msg.type != "text":
                reply = TextReply(content="抱歉，该Agent目前暂时只支持文本消息", message=msg)
                return reply.render()
            # 8. 获取消息内容与发送方账号
            content = msg.content
            openid = msg.target
            wechat_end_user = self.db.session.query(WechatEndUser).filter(
                WechatEndUser.openid == openid,
                WechatEndUser.app_id == app.id
            ).one_or_none()

            # 9. 如果wechat_end_user不存在则创建终端用户并关联记录
            if not wechat_end_user:
                with self.db.auto_commit():
                    end_user = EndUser(tenant_id=app.account_id, app_id=app.id)
                    self.db.session.add(end_user)
                    self.db.session.flush()

                    wechat_end_user = WechatEndUser(
                        openid=openid,
                        app_id=app.id,
                        end_user_id=end_user.id
                    )
                    self.db.session.add(wechat_end_user)

            # 12.判断消息的内容是否为1，并查询未推送的数据
            if content.strip() == "1":
                wechat_message = self.db.session.query(WechatMessage).filter(
                    WechatMessage.wechat_end_user_id == wechat_end_user.id
                ).order_by(desc("created_at")).first()

                if wechat_message and wechat_message.is_pushed is False:
                    # 15. 查询微信消息关联的Agent消息
                    message = self.get(Message, wechat_message.message_id)

                    if message:
                        push_content = ""
                        # 17 根据不同的消息状态执行不同的操作
                        if message.status in [MessageStatus.NORMAL, MessageStatus.STOP]:
                            if message.answer.strip() != "":
                                push_content = message.answer.strip()
                                self.update(wechat_message, is_pushed=True)
                            else:
                                push_content = "该Agent智能体任务正在处理中，请稍后重新回复‘1’获取结果"
                        elif message.status == MessageStatus.TIMEOUT:
                            push_content = "该Agent智能体任务超时，请重新发起提问"
                        elif message.status == MessageStatus.ERROR:
                            push_content = f"该Agent智能体处理任务出错，请重新发起提问，错误信息：{message.error}"
                        reply = TextReply(content=push_content, message=msg)
                        return reply.render()

            # 19. 消息不存在或者已推送，则将'1'作为普通输入
            app_config = self.app_config_service.get_app_config(app)

            # 20 创建一条消息记录与微信消息推送记录
            conversation = wechat_end_user.conversation
            message = self.create(Message, **{
                "app_id": app.id,
                "conversation_id": conversation.id,
                "invoke_from": InvokeFrom.SERVICE_API,
                "created_by": wechat_end_user.end_user_id,
                "query": content,
                "image_urls": [],
                "status": MessageStatus.NORMAL
            })
            self.create(WechatMessage, **{
                "wechat_end_user_id": wechat_end_user.id,
                "message_id": message.id,
                "is_pushed": False
            })

            # 21 创建子纯种，处理Agent对话
            thread = Thread(
                target=self._thread_chat,
                kwargs={
                    "flask_app": current_app._get_current_object(),
                    "app_id": app.id,
                    "app_config": app_config,
                    "conversation_id": conversation.id,
                    "message_id": message.id,
                    "query": content
                }
            )
            thread.start()

            replay = TextReply(content="思考中，请回复'1'获取结果", message=msg)
            return replay.render()

    def _thread_chat(self,
                     flask_app: Flask,
                     app_id: UUID,
                     app_config: dict[str, Any],
                     message_id: UUID,
                     conversation_id: UUID,
                     query: str
                     ):
        """使用子线程创建会话信息，避免数据处理超过5s"""
        with flask_app.app_context():
            # 1.从语言模型中根据模型配置获取模型实例
            app = self.get(App, app_id)
            llm = self.language_model_service.load_language_model(app_config.get("model_config", {}))

            # 2.实例化TokenBufferMemory用于提取短期记忆
            conversation = self.get(Conversation, conversation_id)
            token_buffer_memory = TokenBufferMemory(
                db=self.db,
                conversation=conversation,
                model_instance=llm,
            )
            history = token_buffer_memory.get_history_prompt_messages(
                message_limit=app_config["dialog_round"],
            )

            # 3.将草稿配置中的tools转换成LangChain工具
            tools = self.app_config_service.get_langchain_tools_by_tools_config(app_config["tools"],
                                                                                str(app.account_id))

            # 4.检测是否关联了知识库
            if app_config["datasets"]:
                # 5.构建LangChain知识库检索工具
                dataset_retrieval = self.retrieval_service.create_langchain_tool_from_search(
                    flask_app=flask_app,
                    dataset_ids=[dataset["id"] for dataset in app_config["datasets"]],
                    account_id=app.account_id,
                    retrieval_source=RetrievalSource.APP,
                    **app_config["retrieval_config"],
                )
                tools.append(dataset_retrieval)

            # 6.检测是否关联工作流，如果关联了工作流则将工作流构建成工具添加到tools中
            if app_config["workflows"]:
                workflow_tools = self.app_config_service.get_langchain_tools_by_workflow_ids(
                    [workflow["id"] for workflow in app_config["workflows"]]
                )
                tools.extend(workflow_tools)

            # 6 mcp工具集成
            mcps = []
            if app_config["mcps"]:
                mcps = self.app_config_service.get_mcps_by_mcp_ids(
                    [mcp["id"] for mcp in app_config["mcps"]]
                )

            # 7.根据LLM是否支持tool_call决定使用不同的Agent
            agent_class = FunctionCallAgent if ModelFeature.TOOL_CALL in llm.features else ReactAgent
            agent = agent_class(
                llm=llm,
                agent_config=AgentConfig(
                    user_id=app.account_id,
                    invoke_from=InvokeFrom.DEBUGGER,
                    preset_prompt=app_config["preset_prompt"],
                    enable_long_term_memory=app_config["long_term_memory"]["enable"],
                    tools=tools,
                    review_config=app_config["review_config"],
                    mcps=mcps
                ),
            )

            # 8.定义智能体状态基础数据
            agent_state = {
                "messages": [llm.convert_to_human_message(query, [])],
                "history": history,
                "long_term_memory": conversation.summary,
            }

            # 9.调用智能体获取执行结果
            agent_result = agent.invoke(agent_state)

            # 10.将数据存储到数据库中，包含会话、消息、推理过程
            self.conversation_service.save_agent_thoughts(
                account_id=app.account_id,
                app_id=app.id,
                app_config=app_config,
                conversation_id=conversation.id,
                message_id=message_id,
                agent_thoughts=agent_result.agent_thoughts,
            )
