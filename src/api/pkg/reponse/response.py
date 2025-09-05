from dataclasses import field, dataclass
from typing import Any, Union, Generator

from flask import jsonify, Response as FlaskResponse, stream_with_context

from .http_code import HttpCode


@dataclass
class Response:
    code: HttpCode = HttpCode.SUCCESS
    message: str = ""
    data: Any = field(default_factory=dict)


def json(data: Response = None):
    return jsonify(data), 200


def success_json(data: Any = None):
    return json(Response(code=HttpCode.SUCCESS, message="", data=data))


def fail_json(data: Any = None):
    return json(Response(code=HttpCode.FAIL, message="", data=data))


def validate_error_json(errors: dict = None):
    first_key = next(iter((errors)))
    if first_key is not None:
        msg = errors.get(first_key)[0]
    else:
        msg = ""
    return json(Response(code=HttpCode.VALIDATE_ERROR, message=msg, data=errors))


def message(code: HttpCode = None, msg: str = ""):
    return json(Response(code=code, message=msg, data={}))


def success_message(msg: str = ""):
    return message(HttpCode.SUCCESS, msg)


def fail_message(msg: str = ""):
    return message(HttpCode.FAIL, msg)


def not_found_message(msg: str = ""):
    return message(HttpCode.NOT_FOUNT, msg)


def unauthorized_message(msg: str = ""):
    return message(HttpCode.UNAUTHORIZED, msg)


def forbidden_message(msg: str = ""):
    return message(HttpCode.FORBIDDEN, msg)


def compact_generate_response(response: Union[Response, Generator]) -> FlaskResponse:
    """统一合并处理输出以及流式事件输出"""
    if isinstance(response, Response):
        return json(response)
    else:
        """流式事件输出"""

        def generate() -> Generator:
            yield from response

        return FlaskResponse(
            stream_with_context(generate()),
            status=200,
            mimetype="text/event-stream"
        )
