"""Seed：删 data 表 → 重建 → 导入 CSV → 校验（SDD §5.4 / AC-20）。

幂等：两次执行结果一致。不清空 app schema。
用法：python -m seed.seed
"""
import csv
import logging
import sys
from pathlib import Path

import psycopg

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_DATA_DIR = Path(__file__).resolve().parent / "data"
_SCHEMA_SQL = Path(__file__).resolve().parent / "schema.sql"

# 按外键依赖顺序导入
TABLES = [
    "dim_channel",
    "dim_category",
    "dim_product",
    "dim_customer",
    "dim_store",
    "dim_promotion",
    "promotion_store",
    "dwd_exposure_daily",
    "dwd_ad_daily",
    "dwd_order",
    "dwd_order_detail",
    "dwd_payment",
    "dwd_refund",
    "dwd_order_cost",
]


def _connect():
    return psycopg.connect(settings.database_url, autocommit=True)


def rebuild_schema() -> None:
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA_SQL.read_text(encoding="utf-8"))
    logger.info("data schema 表已重建")


def import_csv(table: str, csv_path: Path) -> int:
    if not csv_path.exists():
        logger.warning("CSV 不存在: %s", csv_path)
        return 0
    with _connect() as conn:
        with conn.cursor() as cur:
            with csv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.reader(f)
                headers = next(reader)
                rows = list(reader)
                if not rows:
                    return 0
                placeholders = ", ".join(["%s"] * len(headers))
                cols = ", ".join(headers)
                cur.executemany(
                    f"INSERT INTO data.{table} ({cols}) VALUES ({placeholders})",
                    rows,
                )
    logger.info("导入 %s: %d 行", table, len(rows))
    return len(rows)


def verify() -> dict:
    """校验行数与 3 个核心指标（GMV/订单数/退款率）。"""
    with _connect() as conn:
        with conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
            counts = {}
            for t in TABLES:
                cur.execute(f"SELECT COUNT(*) AS c FROM data.{t}")
                counts[t] = cur.fetchone()["c"]

            cur.execute(
                "SELECT SUM(pay_amount) AS gmv FROM data.dwd_payment WHERE pay_status='success'"
            )
            gmv = cur.fetchone()["gmv"]

            cur.execute(
                "SELECT COUNT(DISTINCT order_id) AS orders FROM data.dwd_order WHERE order_status IN ('created','paid','refunded')"
            )
            orders = cur.fetchone()["orders"]

            cur.execute(
                "SELECT COUNT(DISTINCT refund_id) AS refunds FROM data.dwd_refund WHERE doc_type='refund'"
            )
            refunds = cur.fetchone()["refunds"]

    refund_rate = round(refunds / orders * 100, 2) if orders else 0
    result = {
        "counts": counts,
        "gmv": float(gmv) if gmv else 0,
        "orders": orders,
        "refund_rate_pct": refund_rate,
    }
    logger.info("校验结果: %s", result)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    rebuild_schema()
    for t in TABLES:
        import_csv(t, _DATA_DIR / f"{t}.csv")
    result = verify()
    print(result)


if __name__ == "__main__":
    main()
