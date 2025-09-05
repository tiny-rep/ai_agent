"""
通用公共异常处理目录
"""
from .exception import (
    CustomException,
    FailException,
    NotFoundException,
    UnauthorizedException,
    ForbiddenException,
    ValidateErrorException
)

__all__ = ["CustomException", "FailException", "NotFoundException",
           "UnauthorizedException", "ForbiddenException", "ValidateErrorException"]
