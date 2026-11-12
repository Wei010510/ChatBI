"""PgCacheStore：读写 app.semantic_cache（SDD §3.5 / §4.4）。

只存 query_spec / sql / chart_spec，不存 rows / narrative。
TTL 默认 CACHE_TTL_SECONDS（7 天）。
"""
from datetime import datetime, timedelta

from ..core.config import get_settings
from ..storage.repository import get_cache, put_cache
from ..storage.session import SessionLocal

settings = get_settings()


class PgCacheStore:
    """算法 CacheStore 协议的 PostgreSQL 实现。"""

    def get(self, key: str) -> dict | None:
        db = SessionLocal()
        try:
            item = get_cache(db, key)
            if item is None:
                return None
            return {
                "query_spec": item.query_spec,
                "sql": item.sql,
                "chart_spec": item.chart_spec,
            }
        finally:
            db.close()

    def put(self, key: str, value: dict) -> None:
        db = SessionLocal()
        try:
            put_cache(
                db,
                cache_key=key,
                query_spec=value.get("query_spec"),
                sql=value.get("sql"),
                chart_spec=value.get("chart_spec"),
                source=value.get("source", "generated"),
            )
        finally:
            db.close()
