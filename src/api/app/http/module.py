import dotenv
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_weaviate import FlaskWeaviate
from injector import Module, Binder, Injector
from redis import Redis

from config import Config
from internal.extension import db, migrate
from internal.extension.login_extension import login_manager
from internal.extension.redis_extension import redis_client
from internal.extension.weaviate_extension import weaviate
from pkg.sqlalchemy import SQLAlchemy

# 将本地.env文件配置项，加载到环境变量中
dotenv.load_dotenv()
conf = Config()


class ExtensionModule(Module):
    def configure(self, binder: Binder) -> None:
        binder.bind(SQLAlchemy, to=db)
        binder.bind(Migrate, to=migrate)
        binder.bind(Redis, to=redis_client)
        binder.bind(LoginManager, to=login_manager)
        binder.bind(FlaskWeaviate, to=weaviate)
        binder.bind(Config, to=conf)


injector = Injector([ExtensionModule])
