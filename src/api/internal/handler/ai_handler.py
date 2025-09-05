from dataclasses import dataclass

from flask_login import login_required, current_user
from injector import inject

from internal.schema.ai_schema import OptimizePromptReq, GenerateSuggesttedQuestionsReq
from internal.service import AIService
from pkg.reponse import validate_error_json, success_json
from pkg.reponse.response import compact_generate_response


@inject
@dataclass
class AIHandler:
    """AI协助"""
    ai_service: AIService

    @login_required
    def optimize_prompt(self):
        """生成优化的预设prompt"""
        req = OptimizePromptReq()
        if not req.validate():
            return validate_error_json(req.errors)

        resp = self.ai_service.optimize_prompt(req.prompt.data)

        return compact_generate_response(resp)

    @login_required
    def generate_suggested_questions(self):
        """生成建议问题"""
        req = GenerateSuggesttedQuestionsReq()
        if not req.validate():
            return validate_error_json(req.errors)

        suggested_questions = self.ai_service.generate_suggested_questions_from_message_id(
            req.message_id.data,
            current_user
        )
        return success_json(suggested_questions)
