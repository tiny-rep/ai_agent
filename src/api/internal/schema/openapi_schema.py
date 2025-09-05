import uuid
from urllib.parse import urlparse

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField, BooleanField
from wtforms.validators import DataRequired, UUID, Optional, ValidationError

from internal.entity.app_entity import AppStatus
from internal.lib.helper import datetime_to_timestamp
from internal.model import App
from .schema import ListField


class OpenAPIChatReq(FlaskForm):
    """开放API聊天接口请求结构体"""
    app_id = StringField("app_id", validators=[
        DataRequired("应用id不能为空"),
        UUID("应用id格式必须为UUID"),
    ])
    end_user_id = StringField("end_user_id", default="", validators=[
        Optional(),
        UUID("终端用户id必须为UUID"),
    ])
    conversation_id = StringField("conversation_id", default="")
    query = StringField("query", default="", validators=[
        DataRequired("用户提问query不能为空"),
    ])
    image_urls = ListField("image_urls", default=[])
    stream = BooleanField("stream", default=True)
    struct_output = StringField("struct_output", default="")  # 需要结构化输出的格式

    def validate_conversation_id(self, field: StringField) -> None:
        """自定义校验conversation_id函数"""
        # 1.检测是否传递数据，如果传递了，则类型必须为UUID
        if field.data:
            try:
                uuid.UUID(field.data)
            except Exception as _:
                raise ValidationError("会话id格式必须为UUID")

            # 2.终端用户id是不是为空
            if not self.end_user_id.data:
                raise ValidationError("传递会话id则终端用户id不能为空")

    def validate_image_urls(self, field: ListField) -> None:
        """校验传递的图片URL链接列表"""
        # 1.校验数据类型如果为None则设置默认值空列表
        if not isinstance(field.data, list):
            return []

        # 2.校验数据的长度，最多不能超过5条URL记录
        if len(field.data) > 5:
            raise ValidationError("上传的图片数量不能超过5，请核实后重试")

        # 3.循环校验image_url是否为URL
        for image_url in field.data:
            result = urlparse(image_url)
            if not all([result.scheme, result.netloc]):
                raise ValidationError("上传的图片URL地址格式错误，请核实后重试")


class GetExLinkAppsWithPageResp(Schema):
    """获取应用分页列表数据响应结构"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    icon = fields.String(dump_default="")
    description = fields.String(dump_default="")
    preset_prompt = fields.String(dump_default="")
    model_config = fields.Dict(dump_default={})
    status = fields.String(dump_default="")
    ex_link_token = fields.String(dump_default="")
    updated_at = fields.Integer(dump_default=0)
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: App, **kwargs):
        app_config = data.app_config if data.status == AppStatus.PUBLISHED else data.draft_app_config
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "preset_prompt": app_config.preset_prompt,
            "model_config": {
                "provider": app_config.model_config.get("provider", ""),
                "model": app_config.model_config.get("model", "")
            },
            "status": data.status,
            "ex_link_token": data.ex_link_token,
            "updated_at": datetime_to_timestamp(data.updated_at),
            "created_at": datetime_to_timestamp(data.created_at),
        }
