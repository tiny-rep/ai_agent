from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.ai_schema import GenerateSuggesttedQuestionsReq
from internal.schema.app_schema import GetAppsWithPageReq
from internal.schema.conversation_schema import GetConversationMessagesWithPageReq, GetConversationMessagesWithPageResp, \
    UpdateConversationNameReq, UpdateConversationIsPinnedReq
from internal.schema.openapi_schema import OpenAPIChatReq, GetExLinkAppsWithPageResp
from internal.service import OpenapiService
from pkg.paginator import PageModel
from pkg.reponse import validate_error_json
from pkg.reponse.response import compact_generate_response, success_json, success_message


@inject
@dataclass
class OpenapiHandler:
    """OpenAPI开放服务"""
    openapi_service: OpenapiService

    @login_required
    def get_conversation_messages_with_page_ex_link(self, conversation_id: UUID, end_user_id: UUID):
        req = GetConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)
        messages, paginator = self.openapi_service.get_conversation_messages_with_page(conversation_id, end_user_id,
                                                                                       req,
                                                                                       current_user)

        resp = GetConversationMessagesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def delete_conversation_ex_link(self, conversation_id: UUID, end_user_id: UUID):
        self.openapi_service.delete_conversation(conversation_id, end_user_id, current_user)

        return success_message("删除会话成功")

    @login_required
    def delete_message_ex_link(self, conversation_id: UUID, end_user_id: UUID, message_id: UUID):
        self.openapi_service.delete_message(conversation_id, end_user_id, message_id, current_user)

        return success_message("删除会话消息成功")

    @login_required
    def get_conversation_name_ex_link(self, conversation_id: UUID, end_user_id: UUID):
        conversation = self.openapi_service.get_conversation(conversation_id, end_user_id, current_user)
        return success_json({"name": conversation.name})

    @login_required
    def update_conversation_name_ex_link(self, conversation_id: UUID, end_user_id: UUID):
        req = UpdateConversationNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.openapi_service.update_conversation(conversation_id, end_user_id, current_user, name=req.name.data)

        return success_message("修改会话名称成功")

    @login_required
    def update_conversation_is_pinned_ex_link(self, conversation_id: UUID, end_user_id: UUID):
        req = UpdateConversationIsPinnedReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.openapi_service.update_conversation(conversation_id, end_user_id, current_user,
                                                 is_pinned=req.is_pinned.data)

        return success_message("修改会话置顶状态成功")

    @login_required
    def chat(self):
        req = OpenAPIChatReq()
        if not req.validate():
            return validate_error_json(req.errors)
        resp = self.openapi_service.chat(req, current_user)
        return compact_generate_response(resp)

    @login_required
    def ex_link_chat(self, ex_link_token: str):
        req = OpenAPIChatReq()
        if not req.validate():
            return validate_error_json(req.errors)
        resp = self.openapi_service.ex_link_chat(req, current_user)
        return compact_generate_response(resp)

    @login_required
    def generate_suggested_questions_in_ex_link(self, end_user_id: UUID):
        """生成建议问题"""
        req = GenerateSuggesttedQuestionsReq()
        if not req.validate():
            return validate_error_json(req.errors)

        suggested_questions = self.openapi_service.generate_suggested_questions_from_message_id_in_ex_link(
            req.message_id.data,
            end_user_id,
            current_user
        )
        return success_json(suggested_questions)

    @login_required
    def init_new_conversation(self,
                              conversation_id: UUID,
                              end_user_id: UUID,
                              app_id: UUID
                              ):
        self.openapi_service.init_new_conversation(conversation_id, end_user_id, app_id, current_user)
        return success_message("初始化会话成功")

    def get_apps_with_page_ex_link(self):

        req = GetAppsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        apps, paginator = self.openapi_service.get_apps_with_page_ex_link(req)

        resp = GetExLinkAppsWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(apps), paginator=paginator))

    def get_hot_apps_with_ex_link(self):
        apps = self.openapi_service.get_hot_apps_with_ex_link()
        resp = GetExLinkAppsWithPageResp(many=True)
        return success_json(resp.dump(apps))
