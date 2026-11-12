"""SQL 物理兜底（SDD §3.2）。

9 条规则中，sql_guard 负责文本/AST 检查（2/6/7/8/9）；
runner 负责连接级兜底（1/3/4/5）。任一不过返回 SQL_REJECTED。
"""
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

# §3.2 写操作黑名单
WRITE_KEYWORDS = {
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "ATTACH", "PRAGMA", "CREATE", "REPLACE", "GRANT", "REVOKE", "MERGE",
}

# §3.2 data schema 白名单（14 张表，电商演示库）
ALLOWED_TABLES = {
    # 维度表
    "dim_channel", "dim_category", "dim_product", "dim_customer",
    "dim_store", "dim_promotion", "promotion_store",
    # 事实表（转化漏斗 + 广告 + 成本）
    "dwd_exposure_daily", "dwd_ad_daily", "dwd_order", "dwd_order_detail",
    "dwd_payment", "dwd_refund", "dwd_order_cost",
}

# 禁止前缀：app. / public.
FORBIDDEN_PREFIXES = ("app.", "public.")


@dataclass
class GuardResult:
    ok: bool
    error: str | None = None
    sql: str = ""  # 可能被改写（补 LIMIT）


def guard_sql(sql: str, max_rows: int = 1000) -> GuardResult:
    """对 SQL 做 5 项检查，返回 GuardResult。

    检查项：
    - 写操作关键字黑名单
    - 禁止 app. / public. 前缀
    - 单条 SELECT（可含 WITH/UNION）
    - 表白名单（data schema 14 张表）
    - 禁止明细查询（无聚合 + 无 GROUP BY）
    """
    # 1. 写操作黑名单（廉价，先做）
    upper = sql.upper()
    for kw in WRITE_KEYWORDS:
        if kw in upper:
            return GuardResult(ok=False, error=f"检测到写操作关键字: {kw}")

    # 2. 禁止 app. / public. 前缀
    lower = sql.lower()
    for prefix in FORBIDDEN_PREFIXES:
        if prefix in lower:
            return GuardResult(ok=False, error=f"禁止访问 {prefix} schema")

    # 3. 解析 + 单条语句
    try:
        parsed = sqlglot.parse(sql)
    except Exception as e:
        return GuardResult(ok=False, error=f"SQL 解析失败: {e}")

    if len(parsed) != 1:
        return GuardResult(ok=False, error=f"只允许单条语句，实际 {len(parsed)} 条")

    statement = parsed[0]
    if not isinstance(statement, (exp.Select, exp.With, exp.Union)):
        return GuardResult(ok=False, error="只允许 SELECT / WITH / UNION 语句")

    # 4. 表白名单（排除 CTE 别名）
    cte_aliases = {c.alias for c in statement.find_all(exp.CTE) if c.alias}
    tables = {t.name for t in statement.find_all(exp.Table)} - cte_aliases
    unknown = tables - ALLOWED_TABLES
    if unknown:
        return GuardResult(ok=False, error=f"引用了未授权的表: {', '.join(sorted(unknown))}")

    # 5. 禁止明细查询：无聚合函数且无 GROUP BY
    has_agg = bool(list(statement.find_all(exp.AggFunc)))
    has_group_by = bool(statement.args.get("group"))
    if not has_agg and not has_group_by:
        return GuardResult(ok=False, error="禁止明细查询：需要聚合或 GROUP BY")

    return GuardResult(ok=True, sql=sql)
