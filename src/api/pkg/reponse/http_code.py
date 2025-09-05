from enum import Enum


class HttpCode(str, Enum):
    """业务状态码"""
    SUCCESS = "success"
    FAIL = "fail"
    NOT_FOUNT = "not_fount"
    UNAUTHORIZED = "unauthorized"  # 未授权
    FORBIDDEN = "forbidden"  # 无权限
    VALIDATE_ERROR = "validate_error"  # 数据验证不通过
