from datetime import datetime
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel


class CurrentTimeArgSchema(BaseModel):
    pass


class CurrentTimeTool(BaseTool):
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        """获取当前系统的时间并进行格式化后返回"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")

    name: str = "current_time"
    description: str = "获取当前系统时间的工具"
    args_schema: Type[BaseModel] = CurrentTimeArgSchema


def current_time(**kwargs) -> BaseTool:
    """返回当前时间的工具"""
    return CurrentTimeTool()
