import mimetypes
import os
from dataclasses import dataclass
from typing import Any

from flask import current_app
from injector import inject
from langchain_openai import ChatOpenAI

from config import Config
from internal.core.language_model.entities.model_entity import BaseLanguageModel, ModelFeature
from internal.core.language_model.language_model_manager import LanguageModelManager
from internal.exception import NotFoundException
from internal.lib.helper import convert_model_to_dict
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService


@inject
@dataclass
class LanguageModelService(BaseService):
    """大语言模型服务"""
    db: SQLAlchemy
    language_model_manager: LanguageModelManager
    conf: Config

    def get_language_models(self) -> list[dict[str, Any]]:
        """获取LLMOps项目中的所有模型列表信息"""
        providers = self.language_model_manager.get_providers()

        language_models = []

        for provider in providers:
            provider_entity = provider.provider_entity
            model_entities = provider.get_model_entities()

            language_model = {
                "name": provider_entity.name,
                "position": provider.position,
                "label": provider_entity.label,
                "icon": provider_entity.icon,
                "description": provider_entity.description,
                "background": provider_entity.background,
                "support_model_types": provider_entity.supported_model_types,
                "models": convert_model_to_dict(model_entities)
            }
            language_models.append(language_model)

        return language_models

    def get_language_model(self, provider_name: str, model_name: str) -> dict[str, Any]:
        """根据传递的提供者名字+模型名字获取模型详细信息"""
        # 1.获取提供者+模型实体信息
        provider = self.language_model_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException("该服务提供者不存在")

        # 2.获取模型实体
        model_entity = provider.get_model_entity(model_name)
        if not model_entity:
            raise NotFoundException("该模型不存在")

        # 3.构建数据并响应
        language_model = convert_model_to_dict(model_entity)

        return language_model

    def get_language_model_icon(self, provider_name: str) -> tuple[bytes, str]:
        """根据传递的提供者名字获取提供商对应的图标信息"""
        # 1.获取提供者信息
        provider = self.language_model_manager.get_provider(provider_name)
        if not provider:
            raise NotFoundException("该服务提供者不存在")

        # 2.获取项目的根路径信息
        root_path = os.path.dirname(os.path.dirname(current_app.root_path))

        # 3.拼接得到提供者所在的文件夹
        provider_path = os.path.join(
            root_path,
            "internal", "core", "language_model", "providers", provider_name,
        )

        # 4.拼接得到icon对应的路径
        icon_path = os.path.join(provider_path, "_asset", provider.provider_entity.icon)

        # 5.检测icon是否存在
        if not os.path.exists(icon_path):
            raise NotFoundException(f"该模型提供者_asset下未提供图标")

        # 6.读取icon的类型
        mimetype, _ = mimetypes.guess_type(icon_path)
        mimetype = mimetype or "application/octet-stream"

        # 7.读取icon的字节数据
        with open(icon_path, "rb") as f:
            byte_data = f.read()
            return byte_data, mimetype

    def load_language_model(self, model_config: dict[str, Any]) -> BaseLanguageModel:
        try:
            provider_name = model_config.get("provider", "")
            model_name = model_config.get("model", "")
            parameters = model_config.get("parameters", {})

            provider = self.language_model_manager.get_provider(provider_name)
            model_entity = provider.get_model_entity(model_name)
            model_class = provider.get_model_class(model_entity.model_type)

            return model_class(
                **model_entity.attributes,
                **parameters,
                features=model_entity.features,
                metadata=model_entity.metadata
            )
        except Exception as _:
            return self.load_default_language_model()

    def load_default_language_model_with_config(self, temperature=1, max_tokens=8192,
                                                features: list[ModelFeature] = None,
                                                metadata: dict[str, Any] = None) -> BaseLanguageModel:
        """根据环境配置获取Model实体"""
        default_provider = self.conf.LLM_DEFAULT_MODEL_PROVIDER
        default_name = self.conf.LLM_DEFAULT_MODEL_NAME
        provider = self.language_model_manager.get_provider(default_provider)
        model_entity = provider.get_model_entity(default_name)
        model_class = provider.get_model_class(model_entity.model_type)
        if features is None:
            features = []
        if metadata is None:
            metadata = {}

        return model_class(
            **model_entity.attributes,
            temperature=temperature,
            max_tokens=max_tokens,
            features=features,
            metadata=metadata
        )

    def load_language_model_pass_openai_with_config(self, temperature=1, max_tokens=8192):
        """通过ChatOpenAI方式加载系统默认配置模型"""
        default_name = self.conf.LLM_DEFAULT_MODEL_NAME
        default_base_url = self.conf.LLM_DEFAULT_MODEL_BASE_URL
        default_api_key = self.conf.LLM_DEFAULT_MODEL_API_KEY
        if not default_base_url or not default_api_key:
            return None
        llm = ChatOpenAI(model=default_name,
                         base_url=default_base_url,
                         temperature=temperature,
                         api_key=default_api_key,
                         max_tokens=max_tokens)
        return llm

    @classmethod
    def load_default_language_model(self) -> BaseLanguageModel:
        default_provider = current_app.config.get("LLM_DEFAULT_MODEL_PROVIDER")
        default_name = current_app.config.get("LLM_DEFAULT_MODEL_NAME")
        provider = self.language_model_manager.get_provider(default_provider)
        model_entity = provider.get_model_entity(default_name)
        model_class = provider.get_model_class(model_entity.model_type)

        return model_class(
            **model_entity.attributes,
            temperature=1,
            max_tokens=8192,
            features=model_entity.features,
            metadata=model_entity.metadata
        )
