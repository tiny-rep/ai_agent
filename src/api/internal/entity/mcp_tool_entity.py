from enum import Enum


class TransportType(str, Enum):
    """Mcp server的传输模式或类型"""
    STDIO = "stdio"
    SSE = "sse"
