"""
将xls数据向量化
"""
import dotenv
import pandas as pd
from langchain_community.vectorstores import FAISS
from redis import Redis

from config import Config
from internal.service.embeddings_service import EmbeddingsService

dotenv.load_dotenv()
conf = Config()


class EmbeddingXLSToFaiss:
    def __init__(self, excel_paths: list[str]):
        self._excel_paths = excel_paths
        self.vector_text = []
        self.metadata = []

    def vector(self):
        for path in self._excel_paths:
            self._read_file(path)

        redis_client = Redis(
            host=conf.REDIS_HOST,
            port=conf.REDIS_PORT,
            db=conf.REDIS_DB,
            password=conf.REDIS_PASSWORD,
            decode_responses=True
        )
        embedding_service = EmbeddingsService(redis_client, conf)
        print("begin embedding")
        db = FAISS.from_texts(
            self.vector_text,
            embedding_service.embeddings,
            # self.metadata,
            relevance_score_fn=lambda distance: 1.0 / (1.0 + distance)
        )
        search_test = db.max_marginal_relevance_search("工作面路口的指示牌上面没有任何内容")
        print(search_test)
        db.save_local("./danger2")

    def _read_file(self, excel_path: str):
        xls_data = pd.read_excel(excel_path)

        for index, row in xls_data.iterrows():
            self.vector_text.append(f"{row['隐患内容']}")
            self.metadata.append({
                "topic": row["隐患专业"],
                "sub_topic": row["专业子类"],
                "level": row["隐患分级"],
                "reform": {
                    "deadline": row["整改期限"],
                    "measure": row["建议整改措施"],
                    "safety_measure": row["安全保障措施"],
                    "penalty_amount": row["处罚金额"]
                }
            })


file_paths = [f"D:\\A04-temp\\01-export-安全专业隐患整理.xlsx",
              f"D:\\A04-temp\\02-export-通风专业隐患整理.xls",
              f"D:\\A04-temp\\03-export-机运专业隐患整理.xls",
              f"D:\\A04-temp\\05-export-采掘专业隐患整理.xls",
              f"D:\\A04-temp\\06-export-地测防治水专业隐患整理.xls",
              f"D:\\A04-temp\\07-export-消防民爆专业隐患整理.xls",
              f"D:\\A04-temp\\08-export-重大隐患整理.xls"]

file_paths = [f"D:\\A04-temp\\02-export-通风专业隐患整理.xls"]
xls_to_faiss = EmbeddingXLSToFaiss(file_paths)
xls_to_faiss.vector()
