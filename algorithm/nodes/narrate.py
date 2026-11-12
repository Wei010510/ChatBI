"""S8 解读：Writer 对查出来的数说一句人话。"""
from .. import llm
from ..config import settings
from ._common import add_trace


def _fallback_narrative(query_spec: dict, rows: list[dict]) -> str:
    """LLM 失败时的规则模板兜底。"""
    metrics = (query_spec or {}).get("metrics", [])
    metric_name = metrics[0] if metrics else "指标"
    if not rows:
        return ""
    first_row = rows[0]
    # 取第一个数值列
    for k, v in first_row.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return f"本期{metric_name}为{v}。"
    return f"已查询{metric_name}。"


def narrate(state, config) -> dict:
    trace = add_trace(state, "narrate", "S8 解读")

    rows = state.get("rows", [])
    # 空结果不调 LLM
    if not rows:
        return {**state, "narrative": "", "trace": trace}

    query_spec = state.get("query_spec", {})
    chart_spec = state.get("chart_spec")
    plan_dict = state.get("plan", {})
    warnings = (state.get("validation") or {}).get("warnings", [])
    degraded = plan_dict.get("degraded", False)

    # rows 摘要最多 20 行
    summary = rows[:20]

    messages = [
        {"role": "system", "content": "你是 ChatBI 的 Writer（S8）。对查出来的数说一句人话，只引用输入数字，不编造、不归因、不建议，≤60字。"},
        {"role": "user", "content": f"问题: {state.get('question', '')}\n指标: {query_spec.get('metrics', [])}\n数据: {summary}\n图表: {chart_spec}\n警告: {warnings}\n降级: {degraded}"},
    ]
    narrative = llm.chat_text(settings.model_mid, messages, temperature=0).strip()

    # 兜底
    if not narrative:
        narrative = _fallback_narrative(query_spec, rows)

    # 截断到 60 字
    if len(narrative) > 60:
        narrative = narrative[:60]

    return {
        **state,
        "narrative": narrative,
        "action": "answer",
        "result": {
            "columns": state.get("columns", []),
            "rows": rows,
            "chart": state.get("chart_spec"),
            "narrative": narrative,
            "truncated": state.get("truncated", False),
        },
        "trace": trace,
    }

