"""QueryResult 数据模型（与算法 §9.2 完全一致）。"""
from typing import Literal, TypedDict


class QueryResult(TypedDict):
    columns: list[dict]
    rows: list[dict]
    row_count: int
    truncated: bool
    elapsed_ms: int
    error_code: Literal["SQL_REJECTED", "SQL_FAILED", "QUERY_TIMEOUT"] | None
    message: str | None
