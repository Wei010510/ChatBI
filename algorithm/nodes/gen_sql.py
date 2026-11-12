"""S5 生成 SQL：Coder 写 SQL + lint 自检回炉（≤2 轮）。"""
from .. import llm
from ..config import settings
from ..exceptions import RejectCode
from ..lint import lint_sql
from ._common import add_trace, get_max_rows

MAX_LINT_ROUNDS = 2


def _table_columns_from_l0(config, tables: list[str]) -> dict[str, list[str]]:
    """从 L0 取「表 → 列名清单」；取不到资源时返回空（lint 规则 4 退化为不校验）。"""
    try:
        l0 = config["configurable"]["resources"].l0() or {}
    except Exception:
        return {}
    wanted = set(tables or [])
    mapping: dict[str, list[str]] = {}
    for col in l0.get("columns") or []:
        tname = str(col.get("table") or "")
        if not tname or (wanted and tname not in wanted):
            continue
        mapping.setdefault(tname, []).append(str(col.get("name") or ""))
    return mapping


def _schema_brief(table_columns: dict[str, list[str]]) -> str:
    return "\n".join(f"{t}({', '.join(cols)})" for t, cols in table_columns.items())


def gen_sql(state, config) -> dict:
    plan_dict = state.get("plan", {})
    few_shot = plan_dict.get("few_shot", [])
    trace = add_trace(
        state,
        "gen_sql",
        "S5 生成 SQL",
        {"few_shot": [str(x.get("id")) for x in few_shot if isinstance(x, dict)]},
    )
    tables = plan_dict.get("tables", [])
    max_rows = get_max_rows(config)

    lint_round = state.get("lint_round", 0)
    lint_errors = state.get("lint_errors", [])

    # 回炉轮次上限
    if lint_round >= MAX_LINT_ROUNDS:
        return {
            **state,
            "action": "reject",
            "reject": {
                "reason_code": RejectCode.SQL_GENERATE_FAILED.value,
                "message": "SQL 生成失败，多次自检未通过",
                "suggestions": [{"label": "换个问法", "question": "请尝试更简单的提问"}],
                "retryable": True,
            },
            "trace": trace,
        }

    # 构造 prompt：首次给 plan + 真实列清单 + few_shot；回炉时追加 lint 报错
    table_columns = _table_columns_from_l0(config, tables)
    schema = _schema_brief(table_columns) or "（未取到库结构）"
    user_content = (
        f"计划: {plan_dict}\n可用表结构: {schema}\n"
        "只能使用上面列出的表名和列名，不要臆造字段。\n"
        f"示例: {few_shot}"
    )
    if lint_errors:
        user_content += f"\n上一版 SQL 的 lint 错误: {lint_errors}\n请只改错的地方。"

    messages = [
        {"role": "system", "content": "你是 ChatBI 的 Coder（S5）。根据 plan 生成一条只读 SQL。只输出 SQL，不要解释。"},
        {"role": "user", "content": user_content},
    ]
    sql = llm.chat_text(settings.model_strong, messages, temperature=0).strip()
    # 去掉可能的 markdown 代码块标记
    sql = sql.replace("```sql", "").replace("```", "").strip()

    # lint 自检
    lint_result = lint_sql(
        sql, allowed_tables=tables, max_rows=max_rows, table_columns=table_columns
    )

    if not lint_result.ok:
        return {
            **state,
            "sql": sql,
            "lint_ok": False,
            "lint_round": lint_round + 1,
            "lint_errors": lint_result.errors,
            "trace": trace,
        }

    # lint 通过
    return {
        **state,
        "sql": sql,
        "lint_ok": True,
        "lint_round": lint_round,
        "lint_errors": [],
        "trace": trace,
    }

