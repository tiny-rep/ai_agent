from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from internal.schema.conversation_schema import GetConversationMessagesWithPageReq, GetConversationMessagesWithPageResp, \
    UpdateConversationNameReq, UpdateConversationIsPinnedReq
from internal.service import ConversationService
from pkg.paginator import PageModel
from pkg.reponse import validate_error_json, success_json, success_message


@inject
@dataclass
class ConversationHandler:
    """会话处理器"""
    conversation_service: ConversationService

    @login_required
    def get_conversation_messages_with_page(self, conversation_id: UUID):
        req = GetConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)
        messages, paginator = self.conversation_service.get_conversation_messages_with_page(conversation_id, req,
                                                                                            current_user)

        resp = GetConversationMessagesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def delete_conversation(self, conversation_id: UUID):
        self.conversation_service.delete_conversation(conversation_id, current_user)

        return success_message("删除会话成功")

    @login_required
    def delete_message(self, conversation_id: UUID, message_id: UUID):
        self.conversation_service.delete_message(conversation_id, message_id, current_user)

        return success_message("删除会话消息成功")

    @login_required
    def get_conversation_name(self, conversation_id: UUID):
        conversation = self.conversation_service.get_conversation(conversation_id, current_user)
        return success_json({"name": conversation.name})

    @login_required
    def update_conversation_name(self, conversation_id: UUID):
        req = UpdateConversationNameReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.conversation_service.update_conversation(conversation_id, current_user, name=req.name.data)

        return success_message("修改会话名称成功")

    @login_required
    def update_conversation_is_pinned(self, conversation_id: UUID):
        req = UpdateConversationIsPinnedReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.conversation_service.update_conversation(conversation_id, current_user, is_pinned=req.is_pinned.data)

        return success_message("修改会话置顶状态成功")
