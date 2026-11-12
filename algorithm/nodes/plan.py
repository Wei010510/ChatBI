"""S4 规划：Planner·规划，唯一拍板者。选表选列、定口径、判可答性。"""
import re
from pathlib import Path

from .. import llm
from ..config import settings
from ..exceptions import RejectCode
from ._common import add_trace, business_reject_payload, get_resources

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "planner_plan.md"

_VAGUE_RE = re.compile(r"怎么样|表现如何|情况如何|好不好")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _valid_window(tr) -> bool:
    """time_range 只有 start/end 都是合法日期才算"有"（SDD §3 S4）。"""
    if not isinstance(tr, dict):
        return False
    return bool(_DATE_RE.match(str(tr.get("start") or ""))) and bool(_DATE_RE.match(str(tr.get("end") or "")))


def _question_mentions_metric(question: str, l1: dict, candidate_metrics: list) -> bool:
    """问句原文是否提到已知指标词（L1 口径 + S3 命中的候选，key/name/alias 都算）。"""
    words = set()
    for m in list(candidate_metrics or []) + list((l1 or {}).get("metrics") or []):
        if not isinstance(m, dict):
            continue
        for w in [m.get("key"), m.get("name"), *(m.get("aliases") or [])]:
            w = str(w or "").strip().lower()
            if w:
                words.add(w)
    q = (question or "").lower()
    return any(w in q for w in words)


def _calendar_options(calendar: dict | None) -> list[dict]:
    """澄清时间窗候选：来自档期日历的真实档期（SDD §3 S4 / §5.2）。"""
    periods = ((calendar or {}).get("promotion") or {}).get("sampled_periods") or []
    options = []
    for p in periods[:4]:
        start, end = str(p.get("start") or ""), str(p.get("end") or "")
        name = str(p.get("name") or "")
        if start and end:
            label = f"{name}（{start[5:]}~{end[5:]}）" if name else f"{start}~{end}"
            options.append({"label": label, "value": f"{start}~{end}"})
    return options


def _metric_options(candidate_metrics: list, l1: dict) -> list[dict]:
    """澄清指标候选：优先 S3 命中的口径候选，兜底 L1 词典前 4 个。"""
    options = []
    for m in candidate_metrics or []:
        name = str((m or {}).get("name") or (m or {}).get("key") or "").strip()
        key = str((m or {}).get("key") or name).strip()
        if name and {"label": name, "value": key} not in options:
            options.append({"label": name, "value": key})
    if not options:
        for m in (l1.get("metrics") or [])[:4]:
            name = str((m or {}).get("name") or (m or {}).get("key") or "").strip()
            key = str((m or {}).get("key") or name).strip()
            if name:
                options.append({"label": name, "value": key})
    return options[:4]


def _enforce_exit_guard(plan_dict: dict, intent_spec: dict, question: str, candidate_metrics: list,
                        l1: dict, calendar: dict | None, data_range: dict):
    """S4 出口的确定性护栏（SDD §3 S4：两类缺槽必须问，显式超时段必须拒，不允许模型放行）。

    返回 (reachable, forced_clarify | None, forced_reject_payload | None)。
    只在模型说 answer 时介入；模型自己说 clarify / reject 时不改写。
    """
    if plan_dict.get("reachable", "answer") != "answer":
        return plan_dict.get("reachable", "answer"), None, None

    # 显式时间整体早于数据起点 → no_data（S1 未拦的兜底，如"去年"被展开成无数据年份）
    tr = plan_dict.get("time_range") or intent_spec.get("time_range") or {}
    min_date = str(data_range.get("min_date") or "")
    end = str(tr.get("end") or "")
    if min_date and end and end < min_date:
        return "reject", None, business_reject_payload(RejectCode.NO_DATA, data_range)

    # 缺指标 → clarify metric（"表现怎么样"类：以问句原文是否提到指标词为准，模型自补不算数）
    vague = bool(_VAGUE_RE.search(question or "")) and not _question_mentions_metric(question, l1, candidate_metrics)
    if vague or not (intent_spec.get("metrics") or plan_dict.get("metrics")):
        return "clarify", {
            "question": "想看哪个指标？和什么基准比（或看哪个时间范围）？",
            "options": _metric_options(candidate_metrics, l1),
            "missing": ["metric"],
        }, None

    # 缺时间窗 → clarify time_range（禁止自行假定全表或"最近 7 天"；start/end 必须都是合法日期）
    if not _valid_window(tr):
        return "clarify", {
            "question": "想看哪个时间范围？",
            "options": _calendar_options(calendar),
            "missing": ["time_range"],
        }, None

    return "answer", None, None


def _norm_options(ambiguity: list) -> list[dict]:
    """澄清选项归一化：字符串与 {label, value} 两种形态都接受（SDD §5.2）。"""
    options = []
    for a in ambiguity or []:
        for opt in (a or {}).get("options", []):
            if isinstance(opt, dict):
                label = str(opt.get("label") or opt.get("value") or "").strip()
                value = str(opt.get("value") or opt.get("label") or "").strip()
            else:
                label = value = str(opt).strip()
            if label and value:
                options.append({"label": label, "value": value})
    return options


def plan(state, config) -> dict:
    resources = get_resources(config)
    trace = add_trace(state, "plan", "S4 规划")

    intent_spec = state.get("intent_spec", {})
    evidence = state.get("evidence", {})
    l0 = resources.l0()
    l1 = resources.l1() or {}
    few_shot = (state.get("plan") or {}).get("few_shot", [])

    # 只把命中的口径候选塞进 prompt，不塞整本字典
    candidate_metrics = evidence.get("metrics") or []
    l1_available = bool(evidence.get("l1_available"))
    calendar = l1.get("calendar") if isinstance(l1, dict) and l1_available else None
    data_range = l0.get("data_range") or {}

    # 调 Planner·规划（temperature=0）
    messages = [
        {"role": "system", "content": _system_prompt()},
        {"role": "user", "content": (
            f"意图: {intent_spec}\n"
            f"表/列证据: {evidence.get('tables', [])} / {evidence.get('columns', [])}\n"
            f"实体证据: {evidence.get('entities', [])}\n"
            f"口径候选: {candidate_metrics}\n"
            f"大促/对比日历: {calendar}\n"
            f"数据范围: {data_range.get('min_date', '?')} ~ {data_range.get('max_date', '?')}\n"
            f"L0表: {l0.get('tables', [])}\n"
            f"口径词典可用: {l1_available}（不可用时按列名与注释推断，必须标 degraded=true）"
        )},
    ]
    plan_dict = llm.chat_json(settings.model_small, messages, temperature=0)

    # 兜底：确保 reachable 存在；词典缺失/为空时强制降级
    reachable = plan_dict.get("reachable", "answer")
    degraded = bool(plan_dict.get("degraded", False)) or not l1_available
    if not l1_available:
        trace.append({"node": "plan", "note": "S4 口径词典缺失或为空，degraded=true"})

    # 出口护栏：只在模型说 answer 时介入（两类缺槽必须问、显式超时段必须拒）
    # 判定「缺指标」时把澄清回填一并视为问句的一部分（用户已答过的槽位不算缺）
    clarify_answer = state.get("clarify_answer") or {}
    clarify_value = str(clarify_answer.get("value") or clarify_answer.get("text") or "").strip()
    guard_question = f"{state.get('question', '')} {clarify_value}".strip()
    reachable, forced_clarify, forced_reject = _enforce_exit_guard(
        plan_dict, intent_spec, guard_question, candidate_metrics, l1, calendar, data_range
    )
    if forced_clarify is not None:
        trace.append({"node": "plan", "note": f"S4 出口护栏：缺 {forced_clarify['missing'][0]}，强制 clarify"})
    if forced_reject is not None:
        trace.append({"node": "plan", "note": "S4 出口护栏：显式时间超出数据范围，强制 reject no_data"})

    # 选表选列存在性校验：只保留 L0 真实存在的表
    valid_tables = {t.get("name") for t in l0.get("tables", [])}
    tables = [t for t in plan_dict.get("tables", []) if t in valid_tables]
    if not tables and l0.get("tables"):
        tables = [l0["tables"][0].get("name")]

    query_spec = {
        "metrics": plan_dict.get("metrics", []),
        "dimensions": plan_dict.get("dimensions", []),
        "filters": plan_dict.get("filters", []),
        "time_range": plan_dict.get("time_range") or intent_spec.get("time_range"),
        "comparison": plan_dict.get("comparison") or intent_spec.get("comparison"),
    }

    result = {
        **state,
        "plan": {
            "tables": tables,
            "metrics": plan_dict.get("metrics", []),
            "dimensions": plan_dict.get("dimensions", []),
            "filters": plan_dict.get("filters", []),
            "time_range": query_spec["time_range"],
            "comparison": query_spec["comparison"],
            "few_shot": few_shot,
            "degraded": degraded,
            "reachable": reachable,
        },
        "query_spec": query_spec,
        "reachable": reachable,
        "trace": trace,
    }

    # clarify 出口
    if reachable == "clarify":
        if forced_clarify is not None:
            options = forced_clarify["options"]
            question = forced_clarify["question"]
            missing = forced_clarify["missing"]
        else:
            options = _norm_options(plan_dict.get("ambiguity", []))
            question = plan_dict.get("clarify_question", "请补充信息")
            missing = plan_dict.get("missing", [])
            # 模型出了澄清卡但没给可点选项：按缺失槽位用真实候选补齐（SDD §5.2）
            if not options and "time_range" in missing:
                options = _calendar_options(calendar)
            if not options and "metric" in missing:
                options = _metric_options(candidate_metrics, l1)
        result["action"] = "clarify"
        result["clarify"] = {
            "clarify_id": f"cl_{state.get('session_id', 'x')}",
            "question": question,
            "options": options or [{"label": "重新描述", "value": "重新描述"}],
            "allow_free_text": True,
            "missing": missing,
        }
        result["clarify_id"] = result["clarify"]["clarify_id"]

    # reject 出口
    elif reachable == "reject":
        result["action"] = "reject"
        result["reject"] = forced_reject or {
            "reason_code": RejectCode.OUT_OF_SCOPE.value,
            "message": plan_dict.get("reject_reason", "无法回答该问题"),
            "suggestions": [],
            "retryable": False,
        }

    return result

