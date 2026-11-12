"""S6 执行节点分流测试。"""
from algorithm.nodes.execute import execute


def _config(runner):
    return {"configurable": {"runner": runner, "cache_store": None, "resources": None, "max_rows": 1000, "timeout_ms": 5000}}


def test_success_goes_to_present(mock_runner):
    state = {"sql": "SELECT 1", "trace": [], "retry_count": 0}
    out = execute(state, _config(mock_runner))
    assert out["rows"] == mock_runner._rows
    assert "action" not in out  # 不 reject，继续 S7


def test_timeout_rejects_no_retry():
    from algorithm.protocols import MockQueryRunner
    runner = MockQueryRunner(error_code="QUERY_TIMEOUT", message="timeout")
    state = {"sql": "SELECT 1", "trace": [], "retry_count": 0}
    out = execute(state, _config(runner))
    assert out["action"] == "reject"
    assert out["reject"]["reason_code"] == "timeout"


def test_first_failure_goes_back_to_s5():
    from algorithm.protocols import MockQueryRunner
    runner = MockQueryRunner(error_code="SQL_FAILED", message="syntax error")
    state = {"sql": "SELECT 1", "trace": [], "retry_count": 0, "lint_round": 0}
    out = execute(state, _config(runner))
    assert out["retry_count"] == 1
    assert out["sql_error"] == "syntax error"
    assert "action" not in out  # 回 S5


def test_second_failure_rejects():
    from algorithm.protocols import MockQueryRunner
    runner = MockQueryRunner(error_code="SQL_FAILED", message="still error")
    state = {"sql": "SELECT 1", "trace": [], "retry_count": 1}
    out = execute(state, _config(runner))
    assert out["action"] == "reject"
    assert out["reject"]["reason_code"] == "sql_execute_failed"


def test_empty_rows_still_answer():
    from algorithm.protocols import MockQueryRunner
    runner = MockQueryRunner(rows=[], columns=[])
    state = {"sql": "SELECT 1", "trace": [], "retry_count": 0}
    out = execute(state, _config(runner))
    assert out["rows"] == []
    assert "action" not in out  # 继续 S7，最终 answer
