"""
weaviate向量数据库操作实例
"""
from dataclasses import dataclass
from typing import Any

from flask import Flask
from flask_weaviate import FlaskWeaviate
from injector import inject
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_weaviate import WeaviateVectorStore
from weaviate.collections import Collection

from .embeddings_service import EmbeddingsService

collection_name = "AGCDatabase"


@inject
@dataclass
class VectorDatabaseService:
    weaviate: FlaskWeaviate
    embeddings_service: EmbeddingsService

    async def _get_client(self, flask_app: Flask):
        with flask_app.app_context():
            return self.weaviate.client

    @property
    def vector_store(self) -> WeaviateVectorStore:
        return WeaviateVectorStore(
            client=self.weaviate.client,
            index_name=collection_name,
            text_key="text",
            embedding=self.embeddings_service.cache_backed_embeddings
        )

    async def add_documents(self, documents: list[Document], **kwargs: Any):
        self.vector_store.add_documents(documents, **kwargs)

    def get_retriever(self) -> VectorStoreRetriever:
        """创建检索器"""
        return self.vector_store.as_retriever()

    def delete_collection(self):
        """删除集合"""
        self.weaviate.client.collections.delete(collection_name)

    @property
    def collection(self) -> Collection:
        """获取向量数据库操作集合"""
        return self.weaviate.client.collections.get(collection_name)
