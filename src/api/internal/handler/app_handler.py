from dataclasses import dataclass
from uuid import UUID

from flask import request
from flask_login import login_required, current_user
from injector import inject

from app.http.module import injector
from internal.schema.app_schema import CreateAppReq, GetAppResp, FallbackHistoryToDraftReq, \
    GetPublishHistoriesWithPageReq, GetPublishHistoriesWithPageResp, UpdateDebugConversationSummaryReq, DebugChatReq, \
    GetDebugConversationMessagesWithPageReq, GetDebugConversationMessagesWithPageResp, UpdateAppReq, GetAppsWithPageReq, \
    GetAppsWithPageResp
from internal.service import AppService, LanguageModelService
from internal.service.retrieval_service import RetrievalService
from pkg.paginator import PageModel
from pkg.reponse import validate_error_json, success_json, success_message
from pkg.reponse.response import compact_generate_response


@inject
@dataclass
class AppHandler:
    """应用控制器"""
    app_service: AppService
    retrieval_service: RetrievalService

    @login_required
    def create_app(self):
        """创建APP"""
        req = CreateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)
        app = self.app_service.create_app(req, current_user)

        return success_json({"id": app.id})

    @login_required
    def update_app(self, app_id: UUID):
        req = UpdateAppReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.app_service.update_app(app_id, current_user, **req.data)

        return success_message("修改Agent智能体应用成功")

    @login_required
    def copy_app(self, app_id: UUID):
        app = self.app_service.copy_app(app_id, current_user)
        return success_json({"id": app.id})

    @login_required
    def delete_app(self, app_id: UUID):
        self.app_service.delete_app(app_id, current_user)
        return success_message("删除Agent智能体应用成功")

    @login_required
    def get_apps_with_page(self):
        req = GetAppsWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        apps, paginator = self.app_service.get_apps_with_page(req, current_user)

        resp = GetAppsWithPageResp(many=True)
        return success_json(PageModel(list=resp.dump(apps), paginator=paginator))

    @login_required
    def get_app(self, app_id: UUID):
        app = self.app_service.get_app(app_id, current_user)
        resp = GetAppResp()
        return success_json(resp.dump(app))

    @login_required
    def get_draft_app_config(self, app_id: UUID):
        draft_config = self.app_service.get_draft_app_config(app_id, current_user)
        return success_json(draft_config)

    @login_required
    def update_draft_app_config(self, app_id: UUID):
        draft_app_config = request.get_json(force=True, silent=True) or {}

        self.app_service.update_draft_app_config(app_id, draft_app_config, current_user)

        return success_message("更新应用草稿配置成功")

    @login_required
    def publish(self, app_id: UUID):
        self.app_service.publish_draft_app_config(app_id, current_user)
        return success_message("发布/更新应用配置成功")

    @login_required
    def cancel_publish(self, app_id: UUID):
        self.app_service.cancel_publish_app_config(app_id, current_user)
        return success_message("取消发布应用配置成功")

    @login_required
    def fallback_history_to_draft(self, app_id: UUID):
        """回滚指定版本到草稿中"""
        req = FallbackHistoryToDraftReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.app_service.fallback_history_to_draft(app_id, req.app_config_version_id.data, current_user)

        return success_message("回退历史配置至草稿成功")

    @login_required
    def get_publish_histories_with_page(self, app_id: UUID):
        req = GetPublishHistoriesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        app_config_versions, paginator = self.app_service.get_publish_histories_with_page(app_id, req, current_user)

        resp = GetPublishHistoriesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(app_config_versions), paginator=paginator))

    @login_required
    def get_debug_conversation_summary(self, app_id: UUID):
        summary = self.app_service.get_debug_conversation_summary(app_id, current_user)
        return success_json({"summary": summary})

    @login_required
    def update_debug_conversation_summary(self, app_id: UUID):
        req = UpdateDebugConversationSummaryReq()
        if not req.validate():
            return validate_error_json(req.errors)

        self.app_service.update_debug_conversation_summary(app_id, req.summary.data, current_user)

        return success_message("更新AI应用长期记忆成功")

    @login_required
    def delete_debug_conversation(self, app_id: UUID):
        self.app_service.delete_debug_conversation(app_id, current_user)
        return success_message("清空应用调试会话记录成功")

    @login_required
    def debug_chat(self, app_id: UUID):
        req = DebugChatReq()
        if not req.validate():
            return validate_error_json(req.errors)
        response = self.app_service.debug_chat(app_id, req, current_user)

        return compact_generate_response(response)

    @login_required
    def stop_debug_chat(self, app_id: UUID, task_id: UUID):
        self.app_service.stop_debug_chat(app_id, task_id, current_user)
        return success_message("停止应用调试会话成功")

    @login_required
    def get_debug_conversation_messages_with_page(self, app_id: UUID):
        req = GetDebugConversationMessagesWithPageReq(request.args)
        if not req.validate():
            return validate_error_json(req.errors)

        messages, paginator = self.app_service.get_debug_conversation_message_with_page(app_id, req, current_user)

        resp = GetDebugConversationMessagesWithPageResp(many=True)

        return success_json(PageModel(list=resp.dump(messages), paginator=paginator))

    @login_required
    def get_published_config(self, app_id: UUID):
        """根据传递的应用id获取应用的发布配置信息"""
        published_config = self.app_service.get_published_config(app_id, current_user)
        return success_json(published_config)

    @login_required
    def regenerate_web_app_token(self, app_id: UUID):
        token = self.app_service.regenerate_web_app_token(app_id, current_user)
        return success_json({"token": token})

    @login_required
    def generate_token_with_ex_link(self, app_id: UUID):
        ex_link_config = self.app_service.generate_token_with_ex_link(app_id, current_user)
        return success_json(ex_link_config)

    @login_required
    def cancel_published_with_ex_link(self, app_id: UUID):
        self.app_service.cancel_published_with_ex_link(app_id, current_user)
        return success_message("取消外链成功")

    @login_required
    def ping(self):
        from internal.core.language_model.language_model_manager import LanguageModelManager

        language_model_manager = LanguageModelManager()
        provider = language_model_manager.get_provider("tongyi")
        model_entity = provider.get_model_entity("qwen-plus")
        language_model_service = injector.get(LanguageModelService)
        llm = language_model_service.load_language_model({
            "provider": "tongyi",
            "model": "qwen-plus"
        })
        print(llm)

        return success_json({
            "content": llm.invoke("你好，你是谁？").content,
            "attrs": model_entity.attributes,
            "features": model_entity.features,
            "metadata": model_entity.metadata
        })
