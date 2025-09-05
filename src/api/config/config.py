import os
from typing import Any

from .default_config import DEFAULT_CONFIG


def _get_env(key: str) -> Any:
    return os.getenv(key, DEFAULT_CONFIG.get(key))


def _get_bool_env(key: str) -> bool:
    value: str = _get_env(key)
    if value is not None:
        return 'true' == value.lower()
    else:
        return False


class Config:
    def __init__(self):
        self.WTF_CSRF_ENABLED = False
        self.SQLALCHEMY_DATABASE_URI = _get_env("SQLALCHEMY_DATABASE_URI")
        self.SQLALCHEMY_TRACK_MODIFICATIONS = _get_bool_env("SQLALCHEMY_TRACK_MODIFICATIONS")
        self.SQLALCHEMY_ENGINE_OPTIONS = {
            "pool_size": int(_get_env("SQLALCHEMY_POOL_SIZE")),
            "pool_recycle": int(_get_env("SQLALCHEMY_POOL_RECYCLE"))
        }
        self.SQLALCHEMY_ECHO = _get_bool_env("SQLALCHEMY_ECHO")

        # Weaviate向量数据库配置
        self.WEAVIATE_HTTP_HOST = _get_env("WEAVIATE_HTTP_HOST")
        self.WEAVIATE_HTTP_PORT = _get_env("WEAVIATE_HTTP_PORT")
        self.WEAVIATE_GRPC_HOST = _get_env("WEAVIATE_GRPC_HOST")
        self.WEAVIATE_GRPC_PORT = _get_env("WEAVIATE_GRPC_PORT")
        self.WEAVIATE_API_KEY = _get_env("WEAVIATE_API_KEY")

        # redis配置
        self.REDIS_HOST = _get_env("REDIS_HOST")
        self.REDIS_PORT = _get_env("REDIS_PORT")
        self.REDIS_USERNAME = _get_env("REDIS_USERNAME")
        self.REDIS_PASSWORD = _get_env("REDIS_PASSWORD")
        self.REDIS_DB = _get_env("REDIS_DB")
        self.REDIS_USE_SSL = _get_bool_env("REDIS_USE_SSL")

        redis_user_pwd = ''
        if len(self.REDIS_PASSWORD) > 0:
            redis_user_pwd = f'{self.REDIS_USERNAME}:{self.REDIS_PASSWORD}@'

        # celery默认配置
        self.CELERY = {
            "broker_url": f"redis://{redis_user_pwd}{self.REDIS_HOST}:{self.REDIS_PORT}/{int(_get_env('CELERY_BROKER_DB'))}",
            "result_backend": f"redis://{redis_user_pwd}{self.REDIS_HOST}:{self.REDIS_PORT}/{int(_get_env('CELERY_RESULT_BACKEND_DB'))}",
            "task_ignore_result": _get_bool_env("CELERY_TASK_IGNORE_RESULT"),
            "result_expires": int(_get_env("CELERY_RESULT_EXPIRES")),
            "broker_connection_retry_on_startup": _get_bool_env("CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP")
        }

        # 辅助Agent应用id标识
        self.ASSISTANT_AGENT_ID = _get_env("ASSISTANT_AGENT_ID")

        # 默认LLM模型
        self.LLM_DEFAULT_MODEL_PROVIDER = _get_env("LLM_DEFAULT_MODEL_PROVIDER")
        self.LLM_DEFAULT_MODEL_NAME = _get_env("LLM_DEFAULT_MODEL_NAME")
        self.LLM_DEFAULT_MODEL_BASE_URL = _get_env("LLM_DEFAULT_MODEL_BASE_URL")
        self.LLM_DEFAULT_MODEL_API_KEY = _get_env("LLM_DEFAULT_MODEL_API_KEY")

        # 系统embedding策略
        self.LLM_EMBEDDING_STRATEGY = _get_env("LLM_EMBEDDING_STRATEGY")
