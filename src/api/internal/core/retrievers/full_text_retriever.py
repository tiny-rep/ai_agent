from collections import Counter
from typing import List
from uuid import UUID

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document as LCDocument
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from internal.model import KeywordTable, Segment
from internal.service.jieba_service import JiebaService
from pkg.sqlalchemy import SQLAlchemy


class FullTextRetriever(BaseRetriever):
    """全文检索器"""
    db: SQLAlchemy
    dataset_ids: list[UUID]
    jieba_service: JiebaService
    search_kwargs: dict = Field(default_factory=dict)

    def _get_relevant_documents(
            self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[LCDocument]:
        """根据query执行关键词检索，获取langchain文档列表"""
        # 1. 根据query转换成关键词列表
        keywords = self.jieba_service.extract_keywords(query, 10)

        # 2. 查询指定知识库的关键词表
        keywords_tables = [
            keyword_table for keyword_table, in
            self.db.session.query(KeywordTable).with_entities(KeywordTable.keyword_table).filter(
                KeywordTable.dataset_id.in_(self.dataset_ids)
            ).all()
        ]

        # 3. 遍历所有的知识库关键词，找到匹配query关键词的Id列表
        all_ids = []
        for keyword_table in keywords_tables:
            # 4. 遍历每一个关键词表的每一项
            for keyword, segment_ids in keyword_table.items():
                # 5. 如果数据存在则提取关键词的就的片段Id列表
                if keyword in keywords:
                    all_ids.extend(segment_ids)

        # 6. 统计segment_id出现的频率，用Counter进行快速统计
        id_counter = Counter(all_ids)

        # 7. 获取频率最高的前K条数，格式：[(segment_id, freq), (segment_id, freq),...]
        k = self.search_kwargs.get("k", 4)
        top_k_ids = id_counter.most_common(k)

        # 8. 根据得到Id列表检索数据库得到的片段列表信息
        segments = self.db.session.query(Segment).filter(
            Segment.id.in_([id for id, _ in top_k_ids])
        ).all()
        segment_dict = {
            str(seg.id): seg for seg in segments
        }

        # 9 根据频率进行排序
        sorted_segments = [segment_dict[str(id)] for id, freq in top_k_ids if id in segment_dict]

        # 10 构建langchain文档对象
        lc_documents = [
            LCDocument(
                page_content=segment.content,
                metadata={
                    "account_id": str(segment.account_id),
                    "dataset_id": str(segment.dataset_id),
                    "document_id": str(segment.document_id),
                    "segment_id": str(segment.id),
                    "node_id": str(segment.node_id),
                    "document_enabled": True,
                    "segment_enabled": True,
                    "score": 0
                }
            )
            for segment in sorted_segments
        ]
        return lc_documents
