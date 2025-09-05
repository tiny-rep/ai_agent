import dotenv

dotenv.load_dotenv()
from langchain_community.vectorstores import FAISS
from redis import Redis

from config import Config
from internal.service.embeddings_service import EmbeddingsService

conf = Config()
redis_client = Redis(
    host=conf.REDIS_HOST,
    port=conf.REDIS_PORT,
    db=conf.REDIS_DB,
    password=conf.REDIS_PASSWORD,
    decode_responses=True
)
embedding_service = EmbeddingsService(redis_client, conf)

db = FAISS.load_local('./danger', embeddings=embedding_service.embeddings, allow_dangerous_deserialization=True)
db2 = FAISS.load_local('./danger2', embeddings=embedding_service.embeddings, allow_dangerous_deserialization=True)
search_test = db.max_marginal_relevance_search("工作面路口的指示牌上面没有任何内容")
print(search_test)
search_test = db2.max_marginal_relevance_search("工作面路口的指示牌上面没有任何内容")
print(search_test)
