from dataclasses import dataclass

import tiktoken
from injector import inject
from langchain.embeddings import CacheBackedEmbeddings
from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.storage import RedisStore
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from redis import Redis

from config import Config


@inject
@dataclass
class EmbeddingsService:
    """文本嵌入模型服务"""
    _store: RedisStore
    _embeddings: Embeddings
    _cache_backed_embeddings: CacheBackedEmbeddings

    def __init__(self, redis: Redis, conf: Config):
        self._store = RedisStore(client=redis)
        # self._embeddings = HuggingFaceEmbeddings(
        #    model_name="Alibaba-NLP/gte-multilingual-base",
        #    cache_folder=os.path.join(os.getcwd(), "internal", "core", "embeddings"),
        #    model_kwargs={
        #        "trust_remote_code": True,
        #    }
        # )
        # 使用默认Embedding配置策略
        embedding_strategy = conf.LLM_EMBEDDING_STRATEGY
        if embedding_strategy == "qwen":
            self._embeddings = DashScopeEmbeddings(model="text-embedding-v3")
        else:
            self._embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        self._cache_backed_embeddings = CacheBackedEmbeddings.from_bytes_store(
            self._embeddings,
            self._store,
            namespace="embeddings"
        )

    @classmethod
    def calculate_token_count(cls, query: str) -> int:
        """计算query的token数"""
        encoding = tiktoken.encoding_for_model("gpt-3.5")
        return len(encoding.encode(query))

    @property
    def store(self) -> RedisStore:
        return self._store

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    @property
    def cache_backed_embeddings(self) -> CacheBackedEmbeddings:
        return self._cache_backed_embeddings
