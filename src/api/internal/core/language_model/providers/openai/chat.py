from langchain_openai import ChatOpenAI

from internal.core.language_model.entities.model_entity import BaseLanguageModel


class Chat(ChatOpenAI, BaseLanguageModel):
    pass
