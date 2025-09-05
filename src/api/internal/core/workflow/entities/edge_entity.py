from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from internal.core.workflow.entities.node_entity import NodeType


class BaseEdgeData(BaseModel):
    """基础边数据"""
    id: UUID
    source: UUID
    source_type: NodeType
    source_handle_id: Optional[UUID]  # 添加起点句柄Id，存在数据时则代表节点存在多个连接句柄
    target: UUID
    target_type: NodeType
