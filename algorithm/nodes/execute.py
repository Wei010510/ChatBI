"""S6 执行：调 QueryRunner，按 error_code 分流。"""
from ..exceptions import RejectCode
from ._common import add_trace, get_runner, get_max_rows, get_timeout_ms


def execute(state, config) -> dict:
    trace = add_trace(state, "execute", "S6 执行 SQL")
    runner = get_runner(config)
    sql = state.get("sql", "")
    max_rows = get_max_rows(config)
    timeout_ms = get_timeout_ms(config)

    retry_count = state.get("retry_count", 0)

    result = runner.run(sql, params=None, timeout_ms=timeout_ms, max_rows=max_rows)
    error_code = result.get("error_code")

    # 成功（含空结果）
    if error_code is None:
        return {
            **state,
            "columns": result.get("columns", []),
            "rows": result.get("rows", []),
            "truncated": result.get("truncated", False),
            "retry_count": retry_count,
            "trace": trace,
        }

    # 超时：不重试
    if error_code == "QUERY_TIMEOUT":
        return {
            **state,
            "action": "reject",
            "reject": {
                "reason_code": RejectCode.TIMEOUT.value,
                "message": "查询超时，请缩小时间范围或减少维度",
                "suggestions": [{"label": "缩小范围", "question": "请缩小查询的时间范围"}],
                "retryable": True,
            },
            "trace": trace,
        }

    # SQL_FAILED / SQL_REJECTED：首次回炉，二次失败
    if retry_count >= 1:
        return {
            **state,
            "action": "reject",
            "reject": {
                "reason_code": RejectCode.SQL_EXECUTE_FAILED.value,
                "message": f"SQL 执行失败: {result.get('message', '')}",
                "suggestions": [{"label": "换个问法", "question": "请尝试其他提问方式"}],
                "retryable": True,
            },
            "trace": trace,
        }

    # 首次失败：带错回 S5 重写
    return {
        **state,
        "sql_error": result.get("message", ""),
        "retry_count": retry_count + 1,
        "lint_round": state.get("lint_round", 0),  # 保持当前 lint 轮次
        "trace": trace,
    }

