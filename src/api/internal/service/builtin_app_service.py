from dataclasses import dataclass

from injector import inject

from internal.core.builtin_apps.builtin_app_manager import BuiltinAppManager
from internal.core.builtin_apps.entities.builtin_app_entity import BuiltinAppEntity
from internal.core.builtin_apps.entities.category_entity import CategoryEntity
from internal.model import Account, App, AppConfigVersion
from pkg.sqlalchemy import SQLAlchemy
from .base_service import BaseService
from ..entity.app_entity import AppStatus, AppConfigType
from ..exception import NotFoundException


@inject
@dataclass
class BuiltinAppService(BaseService):
    """内置应用服务"""
    db: SQLAlchemy
    builtin_app_manager: BuiltinAppManager

    def get_categories(self) -> list[CategoryEntity]:
        return self.builtin_app_manager.get_categories()

    def get_builtin_apps(self) -> list[BuiltinAppEntity]:
        return self.builtin_app_manager.get_builtin_apps()

    def add_builtin_app_to_space(self, builtin_app_id: str, account: Account) -> App:
        """将指定的内置应用添加到个人空间下"""
        builtin_app = self.builtin_app_manager.get_builtin_app(builtin_app_id)
        if not builtin_app:
            raise NotFoundException("该内置应用不存在，请核实后重试")

        with self.db.auto_commit():
            app = App(
                account_id=account.id,
                status=AppStatus.DRAFT,
                **builtin_app.model_dump(include=["name", "icon", "description"])
            )
            self.db.session.add(app)
            self.db.session.flush()

            draft_app_config = AppConfigVersion(
                app_id=app.id,
                model_config=builtin_app.language_model_config,
                config_type=AppConfigType.DRAFT,
                **builtin_app.model_dump(include=[
                    "dialog_round", "preset_prompt", "tools", "retrieval_config", "long_term_memory",
                    "opening_statement", "opening_questions", "speech_to_text", "text_to_speech",
                    "review_config", "suggested_after_answer"
                ])
            )
            self.db.session.add(draft_app_config)
            self.db.session.flush()

            app.draft_app_config_id = draft_app_config.id

        return app
