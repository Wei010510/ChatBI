"""统一响应包装工具。"""
from ..core.logging import trace_id_var


def ok(data) -> dict:
    return {"code": "0", "message": "ok", "data": data, "trace_id": trace_id_var.get()}
