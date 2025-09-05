import io
from dataclasses import dataclass

from flask import send_file
from flask_login import login_required
from injector import inject

from internal.service import LanguageModelService
from pkg.reponse import success_json


@inject
@dataclass
class LanguageModelHandler:
    """大语言模型处理器"""
    language_model_service: LanguageModelService

    @login_required
    def get_language_models(self):
        return success_json(self.language_model_service.get_language_models())

    @login_required
    def get_language_model(self, provider_name: str, model_name: str):
        return success_json(self.language_model_service.get_language_model(provider_name, model_name))

    def get_language_model_icon(self, provider_name: str):
        icon, mimetype = self.language_model_service.get_language_model_icon(provider_name)

        return send_file(io.BytesIO(icon), mimetype)
