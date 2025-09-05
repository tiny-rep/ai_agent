# 默认配置
DEFAULT_CONFIG = {
    "SQLALCHEMY_DATABASE_URI": "postgresql://postgres:postgres@127.0.0.1:5432/gis",
    "SQLALCHEMY_TRACK_MODIFICATIONS": "False",
    "SQLALCHEMY_POOL_SIZE": 30,
    "SQLALCHEMY_POOL_RECYCLE": 3600,

    # Weaviate向量数据库配置
    "WEAVIATE_HTTP_HOST": "localhost",
    "WEAVIATE_HTTP_PORT": 8080,
    "WEAVIATE_GRPC_HOST": "localhost",
    "WEAVIATE_GRPC_PORT": 50051,
    "WEAVIATE_API_KEY": "",

    # Redis数据库配置
    "REDIS_HOST": "localhost",
    "REDIS_PORT": 6379,
    "REDIS_USERNAME": "",
    "REDIS_PASSWORD": "",
    "REDIS_DB": 0,
    "REDIS_USE_SSL": "False",

    # Celery默认配置
    "CELERY_BROKER_DB": 1,
    "CELERY_RESULT_BACKEND_DB": 1,
    "CELERY_TASK_IGNORE_RESULT": "False",
    "CELERY_RESULT_EXPIRES": 3600,
    "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP": "True",

    # 辅助Agent
    "ASSISTANT_AGENT_ID": "6774fcef-b594-8008-b30c-a05b8190afe9",

    # 默认LLM模型
    "LLM_DEFAULT_MODEL_PROVIDER": "openai",
    "LLM_DEFAULT_MODEL_NAME": "gpt-4o-mini",
    "LLM_DEFAULT_MODEL_BASE_URL": "",
    "LLM_DEFAULT_MODEL_API_KEY": "",

    "LLM_EMBEDDING_STRATEGY": "openai"  # 可选 openai, qwen
}
