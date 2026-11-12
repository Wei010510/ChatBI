"""统一异常与 HTTP 错误码映射（SDD §2.5）。"""
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    """应用层统一异常。"""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        http_status: int = 400,
        data: Any = None,
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.data = data
        super().__init__(message)


# 错误码 → HTTP 状态码 映射（SDD §2.5）
ERROR_HTTP_MAP = {
    "INVALID_ARGUMENT": 400,
    "SESSION_NOT_FOUND": 404,
    "REPORT_NOT_FOUND": 404,
    "REPORT_NAME_EXISTS": 409,
    "CLARIFY_EXPIRED": 409,
    "MESSAGE_NOT_QUERYABLE": 422,
    "INTERNAL": 500,
}


class InvalidArgument(AppException):
    def __init__(self, message: str = "参数缺失或格式错误"):
        super().__init__(code="INVALID_ARGUMENT", message=message, http_status=400)


class SessionNotFound(AppException):
    def __init__(self, message: str = "会话不存在"):
        super().__init__(code="SESSION_NOT_FOUND", message=message, http_status=404)


class ReportNotFound(AppException):
    def __init__(self, message: str = "报表不存在"):
        super().__init__(code="REPORT_NOT_FOUND", message=message, http_status=404)


class ReportNameExists(AppException):
    def __init__(self, message: str = "报表名已存在"):
        super().__init__(code="REPORT_NAME_EXISTS", message=message, http_status=409)


class ClarifyExpired(AppException):
    def __init__(self, message: str = "澄清已过期或不存在"):
        super().__init__(code="CLARIFY_EXPIRED", message=message, http_status=409)


class MessageNotQueryable(AppException):
    def __init__(self, message: str = "该消息不可存为报表"):
        super().__init__(code="MESSAGE_NOT_QUERYABLE", message=message, http_status=422)


class InternalError(AppException):
    def __init__(self, message: str = "服务器内部错误"):
        super().__init__(code="INTERNAL", message=message, http_status=500)


async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
    from .logging import trace_id_var

    body = {
        "code": exc.code,
        "message": exc.message,
        "data": None,
        "trace_id": trace_id_var.get(),
    }
    return JSONResponse(status_code=exc.http_status, content=body)


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    from .logging import trace_id_var

    body = {
        "code": "INTERNAL",
        "message": str(exc) or "服务器内部错误",
        "data": None,
        "trace_id": trace_id_var.get(),
    }
    return JSONResponse(status_code=500, content=body)
