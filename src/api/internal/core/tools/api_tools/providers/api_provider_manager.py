from typing import Callable, Type, Optional

import requests
from attr import dataclass
from injector import inject
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

from internal.core.tools.api_tools.entities import ToolEntity
from internal.core.tools.api_tools.entities.openapi_schema import ParameterIn, ParameterTypeMap


@inject
@dataclass
class ApiProviderManager(BaseModel):
    """API工具提供者管理器，能根据传递的工具配置信息生成自定义LangChain工具"""

    @classmethod
    def _create_tool_func_from_tool_entity(cls, tool_entity: ToolEntity) -> Callable:
        def tool_func(**kwargs) -> str:
            # 1. 定义变量存储来自 path/query/header/cookie/request_body中的数据
            parameters = {
                ParameterIn.PATH: {},
                ParameterIn.HEADER: {},
                ParameterIn.QUERY: {},
                ParameterIn.COOKIE: {},
                ParameterIn.REQUEST_BODY: {}
            }

            # 2. 更改参数结构映射
            parameter_map = {parameter.get("name"): parameters for parameter in tool_entity.parameters}
            header_map = {header.get("header"): header for header in tool_entity.headers}

            # 3.遍历传递所有字符并检验
            for key, value in kwargs.items():
                # 4.提取键值对关联的字符并校验
                parameter = parameter_map.get(key)
                if parameter is None:
                    continue
                # 5. 将数据存储到适合的位置
                parameters[parameter.get("in", ParameterIn.QUERY)][key] = value
            # 6. 构建request请求并返回采集的内容
            return requests.request(
                method=tool_entity.method,
                url=tool_entity.url.format(**parameters[ParameterIn.PATH]),
                params=parameters[ParameterIn.QUERY],
                json=parameters[ParameterIn.REQUEST_BODY],
                headers=parameters[ParameterIn.HEADER],
                cookies=parameters[ParameterIn.COOKIE]
            ).text

        return tool_func

    @classmethod
    def _create_model_form_parameters(cls, parameters: list[dict]) -> Type[BaseModel]:
        """根据parameter创建BaseModel"""
        fields = {}
        for parameter in parameters:
            field_name = parameter.get("name")
            field_type = ParameterTypeMap.get(parameter.get("type"), str)
            field_required = parameter.get("required", True)
            field_description = parameter.get("description", "")

            fields[field_name] = (
                field_type if field_required else Optional[field_type],
                Field(description=field_description)
            )
        return create_model("DynamicModel", **fields)

    def get_tool(self, tool_entity: ToolEntity):
        return StructuredTool.from_function(
            func=self._create_tool_func_from_tool_entity(tool_entity),
            name=f"{tool_entity.id}_{tool_entity.name}",
            description=tool_entity.description,
            args_schema=self._create_model_form_parameters(tool_entity.parameters)
        )
