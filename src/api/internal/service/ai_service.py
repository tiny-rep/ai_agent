import json
from dataclasses import dataclass
from typing import Generator
from uuid import UUID

from injector import inject
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from internal.entity.ai_entity import OPTIMIZE_PROMPT_TEMPLATE
from internal.exception import ForbiddenException
from internal.model import Account, Message
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from .conversation_service import ConversationService
from .language_model_service import LanguageModelService


@inject
@dataclass
class AIService(BaseService):
    """AI辅助服务"""
    db: SQLAlchemy
    conversation_service: ConversationService
    language_model_service: LanguageModelService

    def generate_suggested_questions_from_message_id(self,
                                                     message_id: UUID,
                                                     account: Account):
        """生成建议问题列表"""
        message = self.get(Message, message_id)

        if not message or message.created_by != account.id:
            raise ForbiddenException("该条消息不存在或者无权限")

        histories = f"Human:{message.query}\nAI:{message.answer}"

        return self.conversation_service.generate_suggested_questions(histories)

    def optimize_prompt(self, prompt: str) -> Generator[str, None, None]:
        """生成优化后的prompt"""
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", OPTIMIZE_PROMPT_TEMPLATE),
            ("human", "{prompt}")
        ])

        # 使用系统默认LLM模型
        llm = self.language_model_service.load_default_language_model_with_config(0.5)

        optimize_chain = prompt_template | llm | StrOutputParser()

        for optimize_prompt in optimize_chain.stream({"prompt": prompt}):
            data = {"optimize_prompt": optimize_prompt}
            yield f"event: optimize_prompt\ndata:{json.dumps(data)}\n\n"
