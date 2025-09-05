import logging
from dataclasses import dataclass
from datetime import datetime
from threading import Thread
from typing import Any
from uuid import UUID

from flask import Flask, current_app
from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import desc
from sqlalchemy.orm import joinedload

from internal.core.agent.entities.queue_entity import QueueEvent, AgentThought
from internal.entity.conversation_entity import SUMMARIZER_TEMPLATE, CONVERSATION_NAME_TEMPLATE, ConversationInfo, \
    SuggestedQuestions, SUGGESTED_QUESTIONS_TEMPLATE, InvokeFrom, MessageStatus
from internal.exception import NotFoundException
from internal.lib.helper import convert_model_to_dict
from internal.model import MessageAgentThought, Conversation, Message, Account
from internal.schema.conversation_schema import GetConversationMessagesWithPageReq
from pkg.paginator import Paginator
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .language_model_service import LanguageModelService


@inject
@dataclass
class ConversationService(BaseService):
    """会话服务"""
    db: SQLAlchemy
    language_model_service: LanguageModelService

    def summary(self, human_message: str, ai_message: str, old_summary: str) -> str:
        """根据人类消息、AI消息、原始摘要消息等生成新的摘要消息"""
        # 1.创建prompt
        prompt = ChatPromptTemplate.from_template(SUMMARIZER_TEMPLATE)

        # 2. 使用默认模型 创建LLM
        llm = self.language_model_service.load_default_language_model_with_config(0.5)

        # 3. 构建链应用
        summary_chain = prompt | llm | StrOutputParser()

        # 4. 执行链
        new_summary = summary_chain.invoke({
            "summary": old_summary,
            "new_lines": f"Human: {human_message} \nAI: {ai_message}"
        })
        return new_summary

    def generate_conversation_name(self, query: str) -> str:
        """根据query生成对应的会话名字"""
        if len(query) < 4:
            return query

        # 1. 创建prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", CONVERSATION_NAME_TEMPLATE),
            ("human", "{query}")
        ])

        # 2. 使用默认模型 创建LLM
        llm = self.language_model_service.load_language_model_pass_openai_with_config(0.2)
        structured_llm = llm.with_structured_output(ConversationInfo)

        # 3. 构建链应用
        chain = prompt | structured_llm

        # 4. 提取并整理query，截取长度过长的部分
        if len(query) > 2000:
            query = query[:300] + "...[TRUNCATED]..." + query[-300:]
        query = query.replace("\n", " ")

        # 5. 调用链
        conversation_info = chain.invoke({"query": query})

        # 6. 提取会话名字
        name = query[:4]
        try:
            if conversation_info and hasattr(conversation_info, "subject"):
                name = conversation_info.subject
        except Exception as e:
            logging.exception(f"提取会话名称出错，conversation_info:{conversation_info}, 错误：{str(e)}")
        if len(name) > 75:
            name = name[:75] + "..."

        return name

    def generate_suggested_questions(self, histories: str) -> list[str]:
        """根据内容生成三个建议性问题"""
        # 1. 创建prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", SUGGESTED_QUESTIONS_TEMPLATE),
            ("human", "{histories}")
        ])

        # 2. 使用默认模型 创建LLM
        llm = self.language_model_service.load_default_language_model_with_config(0.2)
        structured_llm = llm.with_structured_output(SuggestedQuestions)

        # 3. 构建链应用
        chain = prompt | structured_llm
        # 4. 提取会话名字
        suggested_questions = []
        try:
            # 5. 调用链
            suggested_info = chain.invoke({"histories": histories})
            if suggested_info and hasattr(suggested_info, "questions"):
                suggested_questions = suggested_info.questions
        except Exception as e:
            logging.exception(f"生成建议问题出错，histories:{histories}, 错误：{str(e)}")
        if len(suggested_questions) > 3:
            suggested_questions = suggested_questions[:3]

        return suggested_questions

    def save_agent_thoughts(
            self,
            account_id: UUID,
            app_id: UUID,
            app_config: dict[str, Any],
            conversation_id: UUID,
            message_id: UUID,
            agent_thoughts: list[AgentThought],
    ):
        """存储智能体推理步骤消息"""
        # 1.定义变量存储推理位置及总耗时
        position = 0
        latency = 0
        # 2.在子线程中重新查询conversation以及message，确保对象会被子线程的会话管理到
        conversation = self.get(Conversation, conversation_id)
        message = self.get(Message, message_id)

        # 3.循环遍历所有的智能体推理过程执行存储操作
        for agent_thought in agent_thoughts:
            # 4.存储长期记忆召回、推理、消息、动作、知识库检索等步骤
            if agent_thought.event in [
                QueueEvent.LONG_TERM_MEMORY_RECALL,
                QueueEvent.AGENT_THOUGHT,
                QueueEvent.AGENT_MESSAGE,
                QueueEvent.AGENT_ACTION,
                QueueEvent.DATASET_RETRIEVAL,
                QueueEvent.AGENT_THINK,
                QueueEvent.WORKFLOW_NODE_MESSAGE
            ]:
                # 5.更新位置及总耗时
                position += 1
                latency += agent_thought.latency

                # 6.创建智能体消息推理步骤
                self.create(
                    MessageAgentThought,
                    app_id=app_id,
                    conversation_id=conversation.id,
                    message_id=message.id,
                    invoke_from=InvokeFrom.DEBUGGER,
                    created_by=account_id,
                    position=position,
                    event=agent_thought.event,
                    thought=agent_thought.thought,
                    observation=agent_thought.observation,
                    tool=agent_thought.tool,
                    tool_input=agent_thought.tool_input,
                    # 消息相关字段
                    # modify: 2025-03-26 sam 采用自定义model转换dict函数，处理ollama返回消息不能序列化的现象
                    message=convert_model_to_dict(agent_thought.message),
                    message_token_count=agent_thought.message_token_count,
                    message_unit_price=agent_thought.message_unit_price,
                    message_price_unit=agent_thought.message_price_unit,
                    # 答案相关字段
                    answer=agent_thought.answer,
                    answer_token_count=agent_thought.answer_token_count,
                    answer_unit_price=agent_thought.answer_unit_price,
                    answer_price_unit=agent_thought.answer_price_unit,
                    # 推理统计字段
                    total_token_count=agent_thought.total_token_count,
                    total_price=agent_thought.total_price,
                    latency=agent_thought.latency,
                )

            # 7.检测事件是否为Agent_message
            if agent_thought.event == QueueEvent.AGENT_MESSAGE:
                # 8.更新消息信息
                self.update(
                    message,
                    # 消息相关字段
                    message=agent_thought.message,
                    message_token_count=agent_thought.message_token_count,
                    message_unit_price=agent_thought.message_unit_price,
                    message_price_unit=agent_thought.message_price_unit,
                    # 答案相关字段
                    answer=agent_thought.answer,
                    answer_token_count=agent_thought.answer_token_count,
                    answer_unit_price=agent_thought.answer_unit_price,
                    answer_price_unit=agent_thought.answer_price_unit,
                    # 推理统计字段
                    total_token_count=agent_thought.total_token_count,
                    total_price=agent_thought.total_price,
                    latency=latency,
                )

                # 9.检测是否开启长期记忆
                if app_config["long_term_memory"]["enable"]:
                    Thread(
                        target=self._generate_summary_and_update,
                        kwargs={
                            "flask_app": current_app._get_current_object(),
                            "conversation_id": conversation.id,
                            "query": message.query,
                            "answer": agent_thought.answer
                        }
                    ).start()

                # 10.处理生成新会话名称
                if conversation.is_new:
                    Thread(
                        target=self._generate_conversation_name_and_update,
                        kwargs={
                            "flask_app": current_app._get_current_object(),
                            "conversation_id": conversation.id,
                            "query": message.query
                        }
                    ).start()

            # 11.判断是否为停止或者错误，如果是则需要更新消息状态
            if agent_thought.event in [QueueEvent.TIMEOUT, QueueEvent.STOP, QueueEvent.ERROR]:
                self.update(
                    message,
                    status=agent_thought.event,
                    error=agent_thought.observation,
                )
                break

    def _generate_summary_and_update(self,
                                     flask_app: Flask,
                                     conversation_id: UUID,
                                     query: str,
                                     answer: str):
        with flask_app.app_context():
            conversation = self.get(Conversation, conversation_id)

            new_summary = self.summary(
                query,
                answer,
                conversation.summary
            )

            self.update(
                conversation,
                summary=new_summary
            )

    def _generate_conversation_name_and_update(self,
                                               flask_app: Flask,
                                               conversation_id: UUID,
                                               query: str):
        with flask_app.app_context():
            conversation = self.get(Conversation, conversation_id)
            new_conversation_name = self.generate_conversation_name(query)

            self.update(
                conversation,
                name=new_conversation_name
            )

    def get_conversation(self, conversation_id: UUID, account: Account) -> Conversation:
        """获取指定会话信息"""
        conversation = self.get(Conversation, conversation_id)
        if (
                not conversation
                or conversation.created_by != account.id
                or conversation.is_deleted
        ):
            raise NotFoundException("该会话不存在或者被删除，请核实后重试")

        return conversation

    def get_message(self, message_id: UUID, account: Account) -> Message:
        message = self.get(Message, message_id)
        if (
                not message
                or message.created_by != account.id
                or message.is_deleted
        ):
            raise NotFoundException("该消息不存在或者被删除，请核实后重试")
        return message

    def get_conversation_messages_with_page(self,
                                            conversation_id: UUID,
                                            req: GetConversationMessagesWithPageReq,
                                            account: Account):
        """获取指定会话的消息列表"""
        conversation = self.get_conversation(conversation_id, account)
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

    def delete_conversation(self, conversation_id: UUID, account: Account) -> Conversation:
        conversation = self.get_conversation(conversation_id, account)
        self.update(conversation, is_deleted=True)
        return conversation

    def delete_message(self, conversation_id: UUID, message_id: UUID, account: Account) -> Message:
        conversation = self.get_conversation(conversation_id, account)

        message = self.get_message(message_id, account)

        if conversation.id != message.conversation_id:
            raise NotFoundException("该会话下不存在该消息，请核实后重试")

        self.update(message, is_deleted=True)

        return message

    def update_conversation(self, conversation_id: UUID, account: Account, **kwargs) -> Conversation:
        conversation = self.get_conversation(conversation_id, account)

        self.update(conversation, **kwargs)

        return conversation
