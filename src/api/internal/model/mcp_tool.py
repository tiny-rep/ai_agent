from datetime import datetime

from sqlalchemy import (
    Column, UUID, String, text, Text, PrimaryKeyConstraint, DateTime, Index
)
from sqlalchemy.dialects.postgresql import JSONB

from internal.extension.database_extension import db


class McpTool(db.Model):
    """API工具"""
    __tablename__ = "mcp_tool"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_mcp_tool_id"),
        Index("mcp_tool_account_id_idx", "account_id")
    )

    id = Column(UUID, nullable=False, server_default=text('uuid_generate_v4()'))
    account_id = Column(UUID, nullable=False)
    name = Column(String(255), nullable=False, server_default=text("''::character varying"))
    icon = Column(String(255), nullable=False, server_default=text("''::character varying"))
    description = Column(Text, nullable=False, server_default=text("''::text"))
    transport_type = Column(String(255), nullable=False, server_default=text("''::character varying"))  # stdio、sse
    parameters = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    provider_name = Column(String(255), nullable=False, server_default=text("''::character varying"))
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=text('CURRENT_TIMESTAMP(0)'),
        onupdate=datetime.now
    )
    created_at = Column(DateTime, nullable=False, server_default=text('CURRENT_TIMESTAMP(0)'))
