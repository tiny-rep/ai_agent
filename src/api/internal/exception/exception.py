from dataclasses import field
from typing import Any

from pkg.reponse import HttpCode


class CustomException(Exception):
    code: HttpCode = HttpCode.FAIL
    message: str = "",
    data: Any = field(default_factory=dict)

    def __init__(self, message: str = None, data: Any = None):
        super().__init__()
        self.message = message
        self.data = data


class FailException(CustomException):
    """通用异常"""
    pass


class NotFoundException(CustomException):
    code = HttpCode.NOT_FOUNT


class UnauthorizedException(CustomException):
    code = HttpCode.UNAUTHORIZED


class ForbiddenException(CustomException):
    code = HttpCode.FORBIDDEN


class ValidateErrorException(CustomException):
    code = HttpCode.VALIDATE_ERROR
