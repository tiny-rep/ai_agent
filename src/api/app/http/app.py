# 补丁
from langchain_core.utils import _merge

from config import Config
from internal.core.langchain_fix.langchain_core_utils_merge import merge_lists

# langchain fix补丁包
_merge.merge_lists = merge_lists

from flask_login import LoginManager
from flask_migrate import Migrate
from flask_weaviate import FlaskWeaviate
from flask_cors import CORS

from internal.extension import db
from internal.middleawre import Middleware
from internal.router import Router
from internal.server import Http
from .module import injector

app = Http(__name__,
           static_folder="../../storage/file_storage",
           static_url_path="/static",
           router=injector.get(Router),
           db=db,
           weaviate=injector.get(FlaskWeaviate),
           login_manager=injector.get(LoginManager),
           middleware=injector.get(Middleware),
           migrate=injector.get(Migrate),
           conf=injector.get(Config))
CORS(app, resources={
    r"/openapi/chat": {
        "origins": "*",
        "methods": ["GET", "POST"]
    }
})
celery = app.extensions["celery"]
if __name__ == '__main__':
    app.debug = True
    app.run()
