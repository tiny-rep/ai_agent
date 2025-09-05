from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_weaviate import FlaskWeaviate

from config import Config
from internal.exception import CustomException
from internal.extension import init_log_app, init_redis_app, init_celery_app
from internal.middleawre import Middleware
from internal.router import Router
from pkg.reponse import Response, HttpCode
from pkg.reponse import json
from pkg.sqlalchemy import SQLAlchemy


class Http(Flask):
    """Http应用服务引擎"""

    def __init__(self,
                 *args,
                 conf: Config,
                 db: SQLAlchemy,
                 weaviate: FlaskWeaviate,
                 migrate: Migrate,
                 login_manager: LoginManager,
                 middleware: Middleware,
                 router: Router,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.config.from_object(conf)
        self.register_error_handler(Exception, self._register_error_handler)
        db.init_app(self)
        weaviate.init_app(self)
        init_log_app(self)
        init_redis_app(self)
        init_celery_app(self)
        migrate.init_app(self, db, "internal/migration")
        login_manager.init_app(self)

        login_manager.request_loader(middleware.request_loader)

        router.register_router(self)

    def _register_error_handler(self, error: Exception):

        # 记录日志
        self.logger.error("an error occurend: %s", error, exc_info=True)

        if isinstance(error, CustomException):
            return json(Response(
                code=error.code,
                message=error.message,
                data=error.data
            ))
        if self.debug:
            raise error
        else:
            return json(Response(
                code=HttpCode.FAIL,
                message=str(error),
                data={}
            ))
