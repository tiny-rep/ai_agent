from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms.fields.simple import StringField
from wtforms.validators import DataRequired, regexp, Length, URL

from internal.lib.helper import datetime_to_timestamp
from internal.model import Account
from pkg.password import password_pattern


class GetCurrentUserResp(Schema):
    """获取当前登录账号信息响应"""
    id = fields.UUID(dump_default="")
    name = fields.String(dump_default="")
    email = fields.String(dump_default="")
    avatar = fields.String(dump_default="")
    last_login_at = fields.Integer(dump_default=0)
    last_login_ip = fields.String(dump_default="")
    created_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: Account, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "email": data.email,
            "avatar": data.avatar,
            "last_login_at": datetime_to_timestamp(data.last_login_at),
            "last_login_ip": data.last_login_ip,
            "created_at": datetime_to_timestamp(data.created_at)
        }


class UpdatePasswordReq(FlaskForm):
    """更新账号密码请求"""
    password = StringField("password", validators=[
        DataRequired("登录密码不能为空"),
        regexp(regex=password_pattern, message="密码最少包含一个字母、一个数字，并且长度是8~16")
    ])


class UpdateNameReq(FlaskForm):
    """修改账号名称"""
    name = StringField("name", validators=[
        DataRequired("账号名字不能为空"),
        Length(min=3, max=30, message="账号名字长度在3-30位")
    ])


class UpdateAvatarReq(FlaskForm):
    """修改账号头像"""
    avatar = StringField("avatar", validators=[
        DataRequired(message="账号头像不能为空"),
        URL(message="账号头像必须是URL图片地址")
    ])
