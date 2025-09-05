from typing import Any, List, Dict, get_origin, get_args

from pydantic import Field, create_model


def json_2_model(model_name: str, desc: str, schema: List[Dict[str, Any]]):
    """根据JSON格式创建Pydantic的Model
    schema:[
        {"name": "id", "description": "用户ID", "type": "int", "default": 0},
        {"name": "name", "description": "用户姓名", "type": "str"},
        {"name": "age", "description": "用户年龄", "type": "int", "default": 18},
        {"name": "profile", "description": "用户资料", "type": "dict",
         "sub_schema": [
             {"name": "bio", "description": "个人简介", "type": "str", "default": ""},
             {"name": "hobbies", "description": "爱好列表", "type": "list[str]", "default": []}
         ]},
        {"name": "addresses", "description": "地址列表", "type": "list[dict]",
         "item_schema": [
             {"name": "street", "description": "街道", "type": "str"},
             {"name": "city", "description": "城市", "type": "str"},
             {"name": "zipcode", "description": "邮政编码", "type": "str", "default": ""}
         ]}
    ]
    """
    model = _create_nested_model(model_name, schema)
    model.__doc__ = desc
    return model


def _get_python_type(type_str: str) -> type:
    type_mapping = {
        'string': str,
        'int': int,
        'float': float,
        'bool': bool,
        'dict': dict,
        'list': list,
        'None': type(None)
    }
    return type_mapping.get(type_str, Any)


def _create_nested_model(model_name: str, schema: List[Dict[str, Any]]) -> Any:
    fields = {}
    for field_info in schema:
        field_name: str = field_info['name']
        field_desc: str = field_info['description']
        field_type_str: str = field_info['type']
        field_default_value = field_info.get('default', ...)

        if 'sub_schema' in field_info:
            """子字典"""
            nested_model = _create_nested_model(
                f"{model_name}{field_name.capitalize()}",
                field_info["sub_schema"]
            )
            field_type = nested_model
        elif field_type_str.startswith('list[') and field_type_str.endswith(']'):
            """列表"""
            element_type_str = field_type_str[5:-1].strip()
            if 'item_schema' in field_info:
                element_model = _create_nested_model(
                    f"{model_name}{field_name.capitalize()}Item",
                    field_info['item_schema']
                )
                field_type = List[element_model]
            else:
                element_type = _get_python_type(element_type_str)
                field_type = List[element_type]
        else:
            """基础类型"""
            field_type = _get_python_type(field_type_str)

        # 处理默认值
        if field_default_value is not ...:
            if 'sub_schema' in field_info and isinstance(field_default_value, dict):
                field_default_value = field_type(**field_default_value)
            elif get_origin(field_type) is List:
                element_type = get_args(field_type)[0]
                if hasattr(element_type, '__pydantic_fields__') and all(
                        isinstance(item, dict) for item in field_default_value):
                    field_default_value = [element_type(**item) for item in field_default_value]

        fields[field_name] = (
            field_type,
            Field(
                default=field_default_value,
                description=field_desc
            )
        )
    return create_model(model_name, **fields)
