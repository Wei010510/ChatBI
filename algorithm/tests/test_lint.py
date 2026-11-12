"""lint 五条规则测试。"""
from algorithm.lint import lint_sql


def test_readonly_rejects_write():
    r = lint_sql("DELETE FROM dwd_order", allowed_tables=["dwd_order"])
    assert not r.ok
    assert any("写操作" in e for e in r.errors)


def test_single_statement_rejects_multi():
    r = lint_sql("SELECT 1; SELECT 2", allowed_tables=["dwd_order"])
    assert not r.ok


def test_whitelist_rejects_unknown_table():
    r = lint_sql("SELECT * FROM other_table", allowed_tables=["dwd_order"])
    assert not r.ok
    assert any("未授权" in e for e in r.errors)


def test_limit_added_when_missing():
    r = lint_sql("SELECT pay_amount FROM dwd_order", allowed_tables=["dwd_order"], max_rows=100)
    assert r.ok
    # 规则 5 会补 LIMIT，这里 ok=True 即可（SQL 字符串在实现里被改写但不返回）


def test_valid_sql_passes():
    r = lint_sql("SELECT pay_amount FROM dwd_order LIMIT 10", allowed_tables=["dwd_order"])
    assert r.ok
    assert r.errors == []


def test_cte_name_not_treated_as_table():
    sql = (
        "WITH e AS (SELECT SUM(uv) AS uv FROM dwd_exposure_daily), "
        "p AS (SELECT COUNT(DISTINCT order_id) AS paid FROM dwd_payment) "
        "SELECT p.paid / NULLIF(e.uv, 0) FROM e, p"
    )
    r = lint_sql(sql, allowed_tables=["dwd_exposure_daily", "dwd_payment"])
    assert r.ok
    assert r.errors == []


def test_cte_body_unknown_table_still_rejected():
    sql = "WITH x AS (SELECT * FROM other_table) SELECT * FROM x"
    r = lint_sql(sql, allowed_tables=["dwd_order"])
    assert not r.ok
    assert any("未授权" in e for e in r.errors)


def test_unqualified_hallucinated_column_rejected():
    """单表作用域下，无前缀幻觉列（如 dt）也要被列归属校验拦下。"""
    sql = "SELECT SUM(ad_spend) AS v FROM dwd_ad_daily WHERE dt >= '2026-01-01'"
    r = lint_sql(
        sql,
        allowed_tables=["dwd_ad_daily"],
        table_columns={"dwd_ad_daily": ["stat_date", "ad_spend", "ad_gmv"]},
    )
    assert not r.ok
    assert any("dt" in e for e in r.errors)


def test_real_column_passes_with_metadata():
    sql = "SELECT SUM(ad_spend) AS v FROM dwd_ad_daily WHERE stat_date >= '2026-01-01' LIMIT 10"
    r = lint_sql(
        sql,
        allowed_tables=["dwd_ad_daily"],
        table_columns={"dwd_ad_daily": ["stat_date", "ad_spend", "ad_gmv"]},
    )
    assert r.ok
    assert r.errors == []


def test_prefixed_hallucinated_column_rejected():
    sql = "SELECT p.dt, SUM(p.pay_amount) FROM dwd_payment p GROUP BY p.dt"
    r = lint_sql(
        sql,
        allowed_tables=["dwd_payment"],
        table_columns={"dwd_payment": ["pay_date", "pay_amount", "order_id"]},
    )
    assert not r.ok
    assert any("p.dt" in e for e in r.errors)


def test_cte_output_column_not_flagged():
    """CTE 输出列在 CTE 名下的引用应豁免，不能按真实表校验。"""
    sql = (
        "WITH t AS (SELECT SUM(pay_amount) AS v FROM dwd_payment) "
        "SELECT t.v FROM t LIMIT 10"
    )
    r = lint_sql(
        sql,
        allowed_tables=["dwd_payment"],
        table_columns={"dwd_payment": ["pay_date", "pay_amount", "order_id"]},
    )
    assert r.ok
    assert r.errors == []
