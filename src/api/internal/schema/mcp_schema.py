"""
mcp server配置管理接口的Schema
"""
from urllib.parse import urlparse

from flask_wtf import FlaskForm
from marshmallow import Schema, fields, pre_dump
from wtforms import StringField
from wtforms.validators import DataRequired, Length, URL, AnyOf, Optional, ValidationError

from internal.entity.mcp_tool_entity import TransportType
from internal.model import McpTool
from internal.schema.schema import DictField
from pkg.paginator import PaginatorReq


class CreateMcpToolRequest(FlaskForm):
    """创建mcp server"""
    name = StringField("name", validators=[
        DataRequired("Mcp服务器名称不能为空"),
        Length(min=1, max=30, message="服务器名称长度在1~30")
    ])
    transport_type = StringField("transport_type", validators=[
        DataRequired("传输类型不为空"),
        AnyOf(values=[TransportType.STDIO, TransportType.SSE], message="传输类型错误")
    ])
    icon = StringField("icon", validators=[
        DataRequired("图标不能为空"),
        URL(message="图标必须是图片URL链接"),
    ])
    description = StringField("description", default="", validators=[
        Length(max=800, message="描述的长度不能超过800个字符")
    ])
    provider_name = StringField("provider_name", validators=[
        DataRequired("提供者名称不能为空"),
        Length(min=1, max=100, message="提供者名称长度在1~100")
    ])
    mcp_params = DictField("mcp_params")

    def validate_mcp_params(self, field: DictField) -> None:
        data = field.data
        if not isinstance(data, dict):
            raise ValidationError("配置参数格式错误")
        if self.transport_type.data == TransportType.SSE:
            """sse"""
            if not isinstance(data["host"], str):
                raise ValidationError("Host必须是字符串")
            host_url = urlparse(data["host"])
            if not all([host_url.scheme, host_url.netloc]):
                raise ValidationError("host不是合法的Http协议地址，合法的地址为：http://127.0.0.1:8001/sse")
        elif self.transport_type.data == TransportType.STDIO:
            """stdio"""
            if not isinstance(data["command"], str):
                raise ValidationError("command必须是字符串")
            if not isinstance(data["args"], dict):
                raise ValidationError("args必须是字符串数组")
        else:
            raise ValidationError("类型不支持")


class UpdateMcpToolRequest(FlaskForm):
    """修改mcp server"""
    name = StringField("name", validators=[
        DataRequired("Mcp服务器名称不能为空"),
        Length(min=1, max=30, message="服务器名称长度在1~30")
    ])
    icon = StringField("icon", validators=[
        DataRequired("图标不能为空"),
        URL(message="图标必须是图片URL链接"),
    ])
    transport_type = StringField("transport_type", validators=[
        DataRequired("传输类型不为空"),
        AnyOf(values=[TransportType.STDIO, TransportType.SSE], message="传输类型错误")
    ])
    description = StringField("description", default="", validators=[
        Length(max=800, message="描述的长度不能超过800个字符")
    ])
    provider_name = StringField("provider_name", validators=[
        DataRequired("提供者名称不能为空"),
        Length(min=1, max=100, message="提供者名称长度在1~100")
    ])
    mcp_params = DictField("mcp_params")

    def validate_mcp_params(self, field: DictField) -> None:
        data = field.data
        if not isinstance(data, dict):
            raise ValidationError("配置参数格式错误")
        if self.transport_type.data == TransportType.SSE:
            """sse"""
            if not isinstance(data["host"], str):
                raise ValidationError("Host必须是字符串")
            host_url = urlparse(data["host"])
            if not all([host_url.scheme, host_url.netloc]):
                raise ValidationError("host不是合法的Http协议地址，合法的地址为：http://127.0.0.1:8001/sse")
        elif self.transport_type.data == TransportType.STDIO:
            """stdio"""
            if not isinstance(data["command"], str):
                raise ValidationError("command必须是字符串")
            if not isinstance(data["args"], dict):
                raise ValidationError("args必须是字符串数组")
        else:
            raise ValidationError("类型不支持")


class GetMcpToolsWithPageReq(PaginatorReq):
    """分页查询请求参数"""
    search_word = StringField("search_word", validators=[
        Optional()
    ])


class GetMcpToolsWithPageResp(Schema):
    """分页查询 mcp server list"""
    id = fields.UUID()
    name = fields.String()
    icon = fields.String()
    description = fields.String()
    provider_name = fields.String()
    transport_type = fields.String()
    params = fields.Dict(dump_default=dict)
    created_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: McpTool, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "provider_name": data.provider_name,
            "transport_type": data.transport_type,
            "params": data.parameters,
            "created_at": int(data.created_at.timestamp()),
            "updated_at": int(data.updated_at.timestamp())
        }


class GetMcpToolResp(Schema):
    """分页查询 mcp server list"""
    id = fields.UUID()
    name = fields.String()
    icon = fields.String()
    description = fields.String()
    provider_name = fields.String()
    transport_type = fields.String()
    params = fields.Dict(dump_default=dict)
    created_at = fields.Integer(dump_default=0)
    updated_at = fields.Integer(dump_default=0)

    @pre_dump
    def process_data(self, data: McpTool, **kwargs):
        return {
            "id": data.id,
            "name": data.name,
            "icon": data.icon,
            "description": data.description,
            "provider_name": data.provider_name,
            "transport_type": data.transport_type,
            "params": data.parameters,
            "created_at": int(data.created_at.timestamp()),
            "updated_at": int(data.updated_at.timestamp())
        }
