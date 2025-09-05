from enum import Enum
from typing import Any


class WorkflowStatus(str, Enum):
    """工作流状态类型枚举"""
    DRAFT = "draft"
    PUBLISHED = "published"


class WorkflowResultStatus(str, Enum):
    """工作流运行结果状态"""
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# 工作流默认配置信息，默认添加一个空的工作流
DEFAULT_WORKFLOW_CONFIG = {
    "graph": {},
    "draft_graph": {
        "nodes": [],
        "edges": []
    },
}


class WorkflowDebugGeneratorItemInfo:
    """工作流Debug方法使用，用于多线程传递数据"""
    chunk: Any
    stage: str = ""

    def __init__(self, _stage: str, _chunk: Any):
        self.chunk = _chunk
        self.stage = _stage
