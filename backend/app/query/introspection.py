"""PgIntrospector：L0 元数据读取（SDD §3.6 / §4.2）。

用 DATABASE_META_URL（缺省回落 DATABASE_RO_URL）独立只读连接读 information_schema，
并按 SDD §4.2 补齐：可空 / 主键 / 外键 / 低基数列枚举采样 / 数值列 min-max / 表行数近似。
进程内缓存，schema_version（表名 + 列名 + 类型哈希）变化时重读。
information_schema 读不到 → 抛启动致命异常；单列采样失败只跳过该列并告警。
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from decimal import Decimal
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from ..core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# data schema 14 张表（电商演示库）
DATA_TABLES = [
    # 维度表
    "dim_channel", "dim_category", "dim_product", "dim_customer",
    "dim_store", "dim_promotion", "promotion_store",
    # 事实表（转化漏斗 + 广告 + 成本）
    "dwd_exposure_daily", "dwd_ad_daily", "dwd_order", "dwd_order_detail",
    "dwd_payment", "dwd_refund", "dwd_order_cost",
]

# 事实表日期列：data_range 由 MIN/MAX 聚合得到（库中没有 dim_date）
_FACT_DATE_COLUMNS = [
    ("dwd_payment", "pay_date"),
    ("dwd_order", "order_date"),
    ("dwd_refund", "refund_date"),
]

# 数值类型（取 min / max）
_NUMERIC_TYPES = {
    "smallint", "integer", "bigint", "decimal", "numeric",
    "real", "double precision", "money",
}

# 需要取枚举值的列类型（低基数文本 / 布尔）
_SAMPLED_TYPES = {
    "text", "character varying", "character", "boolean",
}

_LOW_CARD_LIMIT = 50   # distinct 数 ≤ 50 才返回全量枚举值
_SAMPLE_ROWS = 1000    # 单列采样行数上限，避免全表扫
_SAMPLE_TIMEOUT_MS = 5000
_SCHEMA_RECHECK_SECONDS = 300  # 缓存期内不再回查 schema_version（远端库单次往返成本高）


def _to_psycopg_dsn(url: str) -> str:
    """SQLAlchemy 风格 URL → psycopg 可直接使用的 DSN。"""
    return url.replace("postgresql+psycopg://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


def _jsonable(value: Any) -> Any:
    """Decimal / date 等 → JSON 友好类型。"""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


class L0LoadError(Exception):
    """L0 元数据读取失败，启动致命异常。"""


class PgIntrospector:
    def __init__(self, meta_url: str | None = None):
        self._meta_url = _to_psycopg_dsn(meta_url or settings.effective_meta_url)
        self._cache: dict | None = None
        self._cache_at: float = 0.0
        self._schema_version: str = ""

    def l0(self) -> dict:
        now = time.monotonic()
        if self._cache is not None and now - self._cache_at < _SCHEMA_RECHECK_SECONDS:
            return self._cache
        current = self._compute_schema_version()
        if self._cache is not None and current == self._schema_version:
            self._cache_at = now
            return self._cache
        data = self._load_l0(current)
        self._cache = data
        self._schema_version = current
        self._cache_at = now
        return data

    # ---------- schema_version：只含表名 + 列名 + 类型 ----------
    def _compute_schema_version(self) -> str:
        try:
            with psycopg.connect(self._meta_url, autocommit=True) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        SELECT table_name, column_name, data_type
                        FROM information_schema.columns
                        WHERE table_schema = 'data'
                          AND table_name = ANY(%s)
                        ORDER BY table_name, ordinal_position
                        """,
                        (DATA_TABLES,),
                    )
                    rows = cur.fetchall()
        except Exception as e:
            raise L0LoadError(f"读取 information_schema 失败: {e}") from e

        sig = json.dumps([(r["table_name"], r["column_name"], r["data_type"]) for r in rows])
        return hashlib.sha256(sig.encode()).hexdigest()[:16]

    # ---------- 主体 ----------
    def _load_l0(self, schema_version: str) -> dict:
        try:
            with psycopg.connect(self._meta_url, autocommit=True) as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    col_rows = self._read_columns(cur)
                    table_meta = self._read_table_meta(cur)
                    pk_cols = self._read_primary_keys(cur)
                    fk_cols = self._read_foreign_keys(cur)
                    data_range = self._read_data_range(cur)

                    # 采样：逐列执行，失败只跳过该列
                    samples = self._sample_columns(cur, col_rows, table_meta)
        except L0LoadError:
            raise
        except Exception as e:
            raise L0LoadError(f"L0 元数据读取失败: {e}") from e

        return self._assemble(
            col_rows, table_meta, pk_cols, fk_cols, data_range, samples, schema_version
        )

    def _read_columns(self, cur) -> list[dict]:
        cur.execute(
            """
            SELECT table_name, column_name, data_type, is_nullable,
                   col_description(format('data.%%I', table_name)::regclass::oid, ordinal_position) AS comment
            FROM information_schema.columns
            WHERE table_schema = 'data'
              AND table_name = ANY(%s)
            ORDER BY table_name, ordinal_position
            """,
            (DATA_TABLES,),
        )
        return cur.fetchall()

    def _read_table_meta(self, cur) -> dict[str, dict]:
        """表注释 + 行数近似（reltuples 优先，未 analyze 的表回落 n_live_tup，均不做全表 COUNT）。"""
        cur.execute(
            """
            SELECT c.relname AS table_name,
                   obj_description(c.oid, 'pg_class') AS comment,
                   c.reltuples::bigint AS reltuples,
                   s.n_live_tup
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE n.nspname = 'data'
              AND c.relkind = 'r'
              AND c.relname = ANY(%s)
            """,
            (DATA_TABLES,),
        )
        return {r["table_name"]: r for r in cur.fetchall()}

    def _read_primary_keys(self, cur) -> set[tuple[str, str]]:
        # information_schema 在 Supabase 只读角色下看不到约束，直接读 pg_constraint
        cur.execute(
            """
            SELECT c.relname AS table_name, a.attname AS column_name
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey)
            WHERE con.contype = 'p'
              AND n.nspname = 'data'
              AND c.relname = ANY(%s)
            """,
            (DATA_TABLES,),
        )
        return {(r["table_name"], r["column_name"]) for r in cur.fetchall()}

    def _read_foreign_keys(self, cur) -> dict[tuple[str, str], str]:
        cur.execute(
            """
            SELECT c.relname AS table_name, a.attname AS column_name,
                   fc.relname AS ref_table, fa.attname AS ref_column
            FROM pg_constraint con
            JOIN pg_class c ON c.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_class fc ON fc.oid = con.confrelid
            JOIN pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = ANY(con.conkey)
            JOIN pg_attribute fa ON fa.attrelid = con.confrelid AND fa.attnum = ANY(con.confkey)
            WHERE con.contype = 'f'
              AND n.nspname = 'data'
              AND c.relname = ANY(%s)
            """,
            (DATA_TABLES,),
        )
        return {
            (r["table_name"], r["column_name"]): f"{r['ref_table']}.{r['ref_column']}"
            for r in cur.fetchall()
        }

    def _read_data_range(self, cur) -> dict:
        """整体日期范围：从三张事实表的日期列 MIN/MAX 聚合（库中没有 dim_date）。"""
        min_date: Any = None
        max_date: Any = None
        for table, column in _FACT_DATE_COLUMNS:
            try:
                cur.execute(
                    sql.SQL("SELECT MIN({col}) AS mn, MAX({col}) AS mx FROM {tbl}").format(
                        col=sql.Identifier(column),
                        tbl=sql.Identifier("data", table),
                    )
                )
                row = cur.fetchone() or {}
            except Exception as e:
                logger.warning("data_range 读取 %s.%s 失败，已跳过: %s", table, column, e)
                continue
            if row.get("mn") and (min_date is None or row["mn"] < min_date):
                min_date = row["mn"]
            if row.get("mx") and (max_date is None or row["mx"] > max_date):
                max_date = row["mx"]
        return {
            "min_date": _jsonable(min_date),
            "max_date": _jsonable(max_date),
        }

    def _sample_columns(
        self, cur, col_rows: list[dict], table_meta: dict[str, dict]
    ) -> dict[tuple[str, str], dict]:
        """批量采样：数值取 min/max，低基数文本取全部枚举值，高基数只取计数。

        基数先用 pg_stats.n_distinct 预估，超过 50 的列不拉取枚举数组；
        批量失败时回落到逐列采样；单列失败只跳过该列。
        """
        try:
            cur.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(_SAMPLE_TIMEOUT_MS)))
        except Exception as e:
            logger.warning("设置采样 statement_timeout 失败，继续: %s", e)

        stats = self._read_pg_stats(cur)
        samples: dict[tuple[str, str], dict] = {}
        by_table: dict[str, list[dict]] = {}
        for r in col_rows:
            by_table.setdefault(r["table_name"], []).append(r)

        branches = []
        for tname in DATA_TABLES:
            cols = by_table.get(tname) or []
            meta = table_meta.get(tname, {})
            row_est = meta.get("reltuples")
            if row_est is None or row_est < 0:
                row_est = meta.get("n_live_tup")
            items = []
            for r in cols:
                column, dtype = r["column_name"], r["data_type"]
                if dtype in _NUMERIC_TYPES:
                    items.append(
                        sql.SQL("MIN({}) AS {}").format(
                            sql.Identifier(column), sql.Identifier(f"min::{column}")
                        )
                    )
                    items.append(
                        sql.SQL("MAX({}) AS {}").format(
                            sql.Identifier(column), sql.Identifier(f"max::{column}")
                        )
                    )
                elif dtype in _SAMPLED_TYPES:
                    est = self._estimate_distinct(stats.get((tname, column)), row_est)
                    if est is not None and est > _LOW_CARD_LIMIT:
                        # 高基数列只登记计数，不拉取枚举值
                        samples[(tname, column)] = {"distinct_count": est, "enum_values": None}
                        continue
                    items.append(
                        sql.SQL("array_agg(DISTINCT {}) AS {}").format(
                            sql.Identifier(column), sql.Identifier(f"vals::{column}")
                        )
                    )
            if not items:
                continue
            inner = sql.SQL("SELECT {} FROM (SELECT * FROM {} LIMIT {}) s").format(
                sql.SQL(", ").join(items),
                sql.Identifier("data", tname),
                sql.Literal(_SAMPLE_ROWS),
            )
            branches.append(
                sql.SQL(
                    "SELECT {} AS tbl, (SELECT row_to_json(x) FROM ({}) x) AS payload"
                ).format(sql.Literal(tname), inner)
            )

        if not branches:
            return samples

        try:
            cur.execute(sql.SQL(" UNION ALL ").join(branches))
            rows = cur.fetchall()
        except Exception as e:
            logger.warning("批量采样失败，回落逐列采样: %s", e)
            return self._sample_columns_one_by_one(cur, col_rows)

        for row in rows:
            tname = row["tbl"]
            payload = row["payload"] or {}
            for key, value in payload.items():
                kind, _, column = key.partition("::")
                slot = samples.setdefault((tname, column), {})
                if kind == "min":
                    slot["min"] = _jsonable(value)
                elif kind == "max":
                    slot["max"] = _jsonable(value)
                elif kind == "vals":
                    values = [_jsonable(v) for v in (value or [])]
                    slot["distinct_count"] = len(values)
                    slot["enum_values"] = sorted(values, key=str) if len(values) <= _LOW_CARD_LIMIT else None
        return samples

    @staticmethod
    def _estimate_distinct(n_distinct: Any, row_est: Any) -> int | None:
        """pg_stats.n_distinct：正数是精确值，负数是占行数的比例，-1 表示全唯一。"""
        if n_distinct is None:
            return None
        try:
            nd = float(n_distinct)
        except (TypeError, ValueError):
            return None
        if nd >= 0:
            return int(nd)
        if not row_est:
            return None
        return int(abs(nd) * float(row_est))

    def _read_pg_stats(self, cur) -> dict[tuple[str, str], Any]:
        try:
            cur.execute(
                "SELECT tablename, attname, n_distinct FROM pg_stats WHERE schemaname = 'data'"
            )
            return {(r["tablename"], r["attname"]): r["n_distinct"] for r in cur.fetchall()}
        except Exception as e:
            logger.warning("读取 pg_stats 失败，改用采样判定基数: %s", e)
            return {}

    def _sample_columns_one_by_one(self, cur, col_rows: list[dict]) -> dict[tuple[str, str], dict]:
        samples: dict[tuple[str, str], dict] = {}
        for r in col_rows:
            table, column, dtype = r["table_name"], r["column_name"], r["data_type"]
            try:
                if dtype in _NUMERIC_TYPES:
                    samples[(table, column)] = self._sample_numeric(cur, table, column)
                elif dtype in _SAMPLED_TYPES:
                    samples[(table, column)] = self._sample_values(cur, table, column)
            except Exception as e:
                logger.warning("采样 %s.%s 失败，已跳过: %s", table, column, e)
        return samples

    def _sample_numeric(self, cur, table: str, column: str) -> dict:
        cur.execute(
            sql.SQL(
                """
                SELECT MIN({col}) AS mn, MAX({col}) AS mx
                FROM (SELECT {col} FROM {tbl} WHERE {col} IS NOT NULL LIMIT {n}) s
                """
            ).format(
                col=sql.Identifier(column),
                tbl=sql.Identifier("data", table),
                n=sql.Literal(_SAMPLE_ROWS),
            )
        )
        row = cur.fetchone() or {}
        return {"min": _jsonable(row.get("mn")), "max": _jsonable(row.get("mx"))}

    def _sample_values(self, cur, table: str, column: str) -> dict:
        cur.execute(
            sql.SQL(
                """
                SELECT {col} AS v
                FROM (SELECT {col} FROM {tbl} WHERE {col} IS NOT NULL LIMIT {n}) s
                GROUP BY {col}
                ORDER BY {col}
                LIMIT {lim}
                """
            ).format(
                col=sql.Identifier(column),
                tbl=sql.Identifier("data", table),
                n=sql.Literal(_SAMPLE_ROWS),
                lim=sql.Literal(_LOW_CARD_LIMIT + 1),
            )
        )
        values = [_jsonable(r["v"]) for r in cur.fetchall()]
        if not values:
            return {"distinct_count": 0, "enum_values": []}
        if len(values) <= _LOW_CARD_LIMIT:
            return {"distinct_count": len(values), "enum_values": values}
        # 超过 50 个只保留计数（封顶 51 表示 > 50），不返回全量值
        return {"distinct_count": len(values), "enum_values": None}

    # ---------- 组装 ----------
    def _assemble(
        self,
        col_rows: list[dict],
        table_meta: dict[str, dict],
        pk_cols: set[tuple[str, str]],
        fk_cols: dict[tuple[str, str], str],
        data_range: dict,
        samples: dict[tuple[str, str], dict],
        schema_version: str,
    ) -> dict:
        columns_map: dict[str, list[dict]] = {}
        for r in col_rows:
            tname, cname = r["table_name"], r["column_name"]
            sample = samples.get((tname, cname), {})
            col_info = {
                "name": cname,
                "type": r["data_type"],
                "comment": r.get("comment") or cname,
                "nullable": r["is_nullable"] == "YES",
                "is_pk": (tname, cname) in pk_cols,
                "fk": fk_cols.get((tname, cname)),
                "distinct_count": sample.get("distinct_count"),
                "enum_values": sample.get("enum_values"),
                "min": sample.get("min"),
                "max": sample.get("max"),
            }
            columns_map.setdefault(tname, []).append(col_info)

        tables = []
        all_columns = []
        for tname in DATA_TABLES:
            if tname not in columns_map:
                continue
            meta = table_meta.get(tname, {})
            reltuples = meta.get("reltuples")
            row_count_est = (
                reltuples
                if reltuples is not None and reltuples >= 0
                else meta.get("n_live_tup")
            )
            tables.append({
                "name": tname,
                "comment": meta.get("comment") or tname,
                "row_count_est": int(row_count_est) if row_count_est is not None else None,
                "columns": columns_map[tname],
            })
            for c in columns_map[tname]:
                all_columns.append({
                    "table": tname,
                    "name": c["name"],
                    "type": c["type"],
                    "comment": c["comment"],
                })

        return {
            "tables": tables,
            "columns": all_columns,
            "data_range": data_range,
            "schema_version": schema_version,
        }
