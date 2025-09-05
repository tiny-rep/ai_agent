from typing import Tuple

import tiktoken
from langchain_community.chat_models.moonshot import MoonshotChat

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(MoonshotChat, BaseLanguageModel):

    def _get_encoding_model(self) -> Tuple[str, tiktoken.Encoding]:
        """重写获取编码模型名字+模型函数，该类继续OpenAI，词表模型可以使用gpt-3.5-turbo防止出错"""
        model = "gpt-3.5-turbo"
        return model, tiktoken.encoding_for_model(model)
