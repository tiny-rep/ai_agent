import importlib
import random
import socket
import string
from datetime import datetime
from enum import Enum
from hashlib import sha3_256
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from langchain_core.documents import Document
from pydantic import BaseModel, HttpUrl


def dynamic_import(module_name: str, symbol_name: str) -> Any:
    """动态导入模块下的特定功能 t"""
    module = importlib.import_module(module_name)
    return getattr(module, symbol_name)


def add_attribute(attr_name: str, attr_value: Any):
    """装饰器函数，为特定的函数添加相应的属性，第一个参数为属性名字，第二个参数为属性值"""

    def decorator(func):
        setattr(func, attr_name, attr_value)
        return func

    return decorator


def datetime_to_timestamp(dt: datetime) -> int:
    if dt is None:
        return 0
    return int(dt.timestamp())


def generate_text_hash(text: str) -> str:
    """计算传入的文本的hash字符串"""
    text = str(text) + "None"
    return sha3_256(text.encode()).hexdigest()


def combine_documents(documents: list[Document]) -> str:
    """将对应的文档列表使用换行符进行合并"""
    return "\n\n".join([document.page_content for document in documents])


def remove_fields(data_dict: dict, fields: list[str]) -> None:
    """根据传递的字段名移除字典中指定的字段"""
    for field in fields:
        data_dict.pop(field, None)


def convert_model_to_dict(obj: Any, *args, **kwargs):
    """将pydantic v1版本中的UUID/Enum函数转换成可序列化存储的数据"""
    if isinstance(obj, BaseModel):
        obj_dict = obj.dict(*args, **kwargs)
        for key, value in obj_dict.items():
            obj_dict[key] = convert_model_to_dict(value, *args, **kwargs)
        return obj_dict
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, HttpUrl):
        return str(obj)
    elif isinstance(obj, list):
        return [convert_model_to_dict(item, *args, **kwargs) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_model_to_dict(value, *args, **kwargs) for key, value in obj.items()}
    return obj


def get_value_type(value: Any) -> Any:
    """根据传递的变量获取变量的类型，并将str和bool转为string和boolean"""
    value_type = type(value).__name__

    if value_type == 'str':
        return "string"
    elif value_type == "bool":
        return "boolean"

    return value_type


def generate_random_string(length: int = 16) -> str:
    """生成随机字符串"""
    chars = string.ascii_letters + string.digits

    random_str = ''.join(random.choices(chars, k=length))

    return random_str


def check_http_server(url: str):
    """验证Http服务器是否正常"""
    _url_obj = urlparse(url)
    netloc = _url_obj.netloc
    tmp = netloc.split(':')
    ip = tmp[0]
    port = tmp[1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    try:
        sock.connect((ip, int(port)))
        return True
    except socket.error:
        return False
    finally:
        sock.close()
