"""PgQueryRunner：SQL 物理兜底 + 执行 + 归一化（SDD §3）。

只读连接 DATABASE_RO_URL，search_path=data，外层 LIMIT+1 截断，
statement_timeout，参数化，结果归一化。
"""
from __future__ import annotations

import time
from typing import Any

import psycopg
from psycopg.rows import dict_row

from ..core.config import get_settings
from .models import QueryResult
from .sql_guard import guard_sql

settings = get_settings()

# PG 类型 OID → 归一化 type 映射（psycopg3 的 Column 只提供 type_code）
_PG_INT_OIDS = {20, 21, 23}
_PG_FLOAT_OIDS = {700, 701, 1700}
_PG_NUMERIC_OIDS = _PG_INT_OIDS | _PG_FLOAT_OIDS
_PG_DATE_OIDS = {1082, 1083, 1114, 1184, 1266}


def _map_type(type_code: int) -> str:
    if type_code in _PG_NUMERIC_OIDS:
        return "number"
    if type_code in _PG_DATE_OIDS:
        return "date"
    return "string"


def _normalize_value(value: Any, type_code: int) -> Any:
    if value is None:
        return None
    if type_code in _PG_NUMERIC_OIDS:
        # int 类型转 int，浮点转 float
        return int(value) if type_code in _PG_INT_OIDS else float(value)
    if type_code in _PG_DATE_OIDS:
        # 日期/时间转 ISO 字符串
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return str(value)
    return value


class PgQueryRunner:
    """算法 QueryRunner 协议的 PostgreSQL 实现。"""

    def __init__(self, ro_url: str | None = None):
        self._ro_url = ro_url or settings.database_ro_url

    def run(
        self,
        sql: str,
        *,
        params: dict | None = None,
        timeout_ms: int | None = None,
        max_rows: int | None = None,
    ) -> QueryResult:
        timeout_ms = timeout_ms or settings.query_timeout_ms
        max_rows = max_rows or settings.max_rows
        start = time.monotonic()

        # 物理兜底：sql_guard 检查
        guard = guard_sql(sql, max_rows=max_rows)
        if not guard.ok:
            return QueryResult(
                columns=[],
                rows=[],
                row_count=0,
                truncated=False,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                error_code="SQL_REJECTED",
                message=guard.error,
            )

        # 外层包 LIMIT max_rows+1 截断
        wrapped = f"SELECT * FROM ({sql.rstrip().rstrip(';')}) t LIMIT {max_rows + 1}"

        try:
            with psycopg.connect(self._ro_url, autocommit=True) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    # search_path=data + statement_timeout
                    cur.execute("SET search_path = data")
                    cur.execute(f"SET LOCAL statement_timeout = {int(timeout_ms)}")
                    cur.execute(wrapped, params or {})
                    raw_rows = cur.fetchall()
                    col_desc = cur.description or []
        except psycopg.errors.QueryCanceled:
            return QueryResult(
                columns=[], rows=[], row_count=0, truncated=False,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                error_code="QUERY_TIMEOUT", message="查询超时",
            )
        except Exception as e:
            return QueryResult(
                columns=[], rows=[], row_count=0, truncated=False,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                error_code="SQL_FAILED", message=str(e),
            )

        # 归一化列
        columns = []
        for col in col_desc:
            pg_type = col.type_code
            columns.append({
                "key": col.name,
                "title": col.name,  # title 取注释（此处无注释回退列名）
                "type": _map_type(pg_type),
            })

        # 归一化行 + 截断判断
        truncated = len(raw_rows) > max_rows
        rows = []
        for raw in raw_rows[:max_rows]:
            row = {}
            for col in col_desc:
                row[col.name] = _normalize_value(raw.get(col.name), col.type_code)
            rows.append(row)

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            elapsed_ms=int((time.monotonic() - start) * 1000),
            error_code=None,
            message=None,
        )
