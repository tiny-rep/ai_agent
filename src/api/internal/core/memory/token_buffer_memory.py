from dataclasses import dataclass

from langchain_core.messages import AnyMessage, AIMessage, trim_messages, get_buffer_string
from sqlalchemy import desc

from internal.core.language_model.entities.model_entity import BaseLanguageModel
from internal.entity.conversation_entity import MessageStatus
from internal.model import Conversation, Message
from pkg.sqlalchemy import SQLAlchemy


@dataclass
class TokenBufferMemory:
    """基于Token计数的缓冲记忆组件"""
    db: SQLAlchemy
    conversation: Conversation
    model_instance: BaseLanguageModel

    def get_history_prompt_messages(self,
                                    max_token_limit: int = 2000,
                                    message_limit: int = 10) -> list[AnyMessage]:
        """根据token限制+消息条数限制获取指定会话模型的历史消息列表"""

        # 1. 判断会话模型是否存在
        if self.conversation is None:
            return []

        # 2. 查询该会话的消息列表，并且使用时间进行倒序，同时匹配答案不为空、匹配会话Id、没有软删除、状态是正常
        messages = self.db.session.query(Message).filter(
            Message.conversation_id == self.conversation.id,
            Message.answer != "",
            Message.is_deleted == False,
            Message.status.in_([MessageStatus.TIMEOUT, MessageStatus.STOP, MessageStatus.NORMAL])
        ).order_by(desc("created_at")).limit(message_limit).all()
        messages = list(reversed(messages))

        # 3. 将messages转换为langChain消息列表
        prompt_messages = []
        for message in messages:
            prompt_messages.extend([
                self.model_instance.convert_to_human_message(message.query, message.image_urls),
                AIMessage(content=message.answer)
            ])

        # 4. 调用langchain的trim_messages函数剪切消息列表
        return trim_messages(
            messages=prompt_messages,
            max_tokens=max_token_limit,
            token_counter=self.model_instance,
            strategy="last",
            start_on="human",
            end_on="ai"
        )

    def get_history_prompt_text(self,
                                human_prefix: str = "human",
                                ai_prefix: str = "ai",
                                max_token_limit: int = 2000,
                                message_limit: int = 10
                                ) -> str:
        """根据指定的会话获取消息提示文本"""
        messages = self.get_history_prompt_messages(max_token_limit, message_limit)

        return get_buffer_string(messages, human_prefix, ai_prefix)
