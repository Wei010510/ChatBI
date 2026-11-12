"""sql_guard 9 条兜底测试（AC-5）。"""
from app.query.sql_guard import guard_sql


class TestSqlGuard:
    def test_write_insert_rejected(self):
        r = guard_sql("INSERT INTO dwd_order VALUES (1)")
        assert not r.ok
        assert "INSERT" in (r.error or "")

    def test_write_delete_rejected(self):
        r = guard_sql("DELETE FROM dwd_order")
        assert not r.ok

    def test_app_schema_rejected(self):
        r = guard_sql("SELECT * FROM app.sessions")
        assert not r.ok
        assert "app." in (r.error or "")

    def test_public_schema_rejected(self):
        r = guard_sql("SELECT * FROM public.exemplar_embeddings")
        assert not r.ok

    def test_multi_statement_rejected(self):
        r = guard_sql("SELECT 1; SELECT 2")
        assert not r.ok

    def test_non_select_rejected(self):
        r = guard_sql("SHOW TABLES")
        assert not r.ok

    def test_unknown_table_rejected(self):
        r = guard_sql("SELECT COUNT(*) FROM unknown_table")
        assert not r.ok
        assert "未授权的表" in (r.error or "")

    def test_detail_query_rejected(self):
        r = guard_sql("SELECT order_id, pay_amount FROM dwd_order")
        assert not r.ok
        assert "明细" in (r.error or "")

    def test_agg_select_allowed(self):
        r = guard_sql("SELECT channel, SUM(pay_amount) FROM dwd_order GROUP BY channel")
        assert r.ok

    def test_count_allowed(self):
        r = guard_sql("SELECT COUNT(*) AS cnt FROM dwd_order")
        assert r.ok

    def test_with_clause_allowed(self):
        r = guard_sql(
            "WITH t AS (SELECT channel, SUM(pay_amount) AS gmv FROM dwd_order GROUP BY channel) "
            "SELECT * FROM t"
        )
        assert r.ok
