"""S1 理解：Planner·理解，把人话翻成结构化意图，只翻译不判断。"""
import json
import re

from .. import llm
from ..config import settings
from ..exceptions import RejectCode
from ._common import add_trace, business_reject_payload, get_resources

# 三类范围问题关键词（命中即拒答，SDD §2.3）；no_data 不走关键词，走 data_range 动态比对
SCOPE_KEYWORDS = {
    RejectCode.WRITE_OP: ["insert", "update", "delete", "drop", "alter", "修改", "删除", "写入", "改数", "改成", "改为", "设为", "更新数据"],
    RejectCode.DETAIL_EXPORT: ["导出明细", "导出行", "下载明细", "导出全部", "导出所有订单"],
    RejectCode.OUT_OF_SCOPE: ["竞品", "友商", "竞对", "外部数据", "行业大盘", "友商销量"],
}

_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")
_DATE_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s*[~～—\-至到]+\s*(\d{4}-\d{2}-\d{2})")


def _check_scope(question: str) -> RejectCode | None:
    lower = question.lower()
    for code, keywords in SCOPE_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in lower:
                return code
    return None


def _get_data_range(config) -> dict:
    """从注入的 resources 取 L0 data_range；取不到返回空表（跳过 no_data 拦截）。"""
    try:
        resources = get_resources(config)
        if resources is None:
            return {}
        return (resources.l0() or {}).get("data_range") or {}
    except Exception:
        return {}


def _check_no_data(question: str, data_range: dict) -> bool:
    """问题里的显式年份全部落在 data_range 之外 → no_data（SDD §2.3，禁止年份关键词表）。"""
    if not data_range:
        return False
    years = [int(y) for y in _YEAR_RE.findall(question)]
    if not years:
        return False
    try:
        min_year = int(str(data_range.get("min_date") or "")[:4])
        max_year = int(str(data_range.get("max_date") or "")[:4])
    except (TypeError, ValueError):
        return False
    if not min_year or not max_year:
        return False
    return all(y < min_year for y in years) or all(y > max_year for y in years)


def _business_reject(state, code: RejectCode, trace, data_range: dict | None = None) -> dict:
    return {
        **state,
        "action": "reject",
        "reject": business_reject_payload(code, data_range),
        "trace": trace,
    }


def _can_merge_deterministically(value: str, config) -> bool:
    """该澄清值能否确定性写槽（时间窗格式 / L1 口径 key·name·alias 精确命中）。

    能命中就不再把值拼进问题让 LLM 重理解（SDD-后端 §2.2），与 _merge_clarify_answer 的合并条件保持一致。
    """
    if _DATE_RANGE_RE.search(value):
        return True
    try:
        resources = get_resources(config)
        l1 = (resources.l1() or {}) if resources is not None else {}
    except Exception:
        l1 = {}
    for metric in l1.get("metrics") or []:
        if not isinstance(metric, dict):
            continue
        names = {str(metric.get("key") or ""), str(metric.get("name") or "")}
        names.update(str(a) for a in (metric.get("aliases") or []))
        names.discard("")
        if value in names:
            return True
    return False


def _merge_clarify_answer(intent_spec: dict, clarify_answer: dict, config) -> dict:
    """澄清回填：能结构化的确定性写槽位，不过 NLU（SDD §5.2）；其余已在 LLM 问题里并入。"""
    value = str((clarify_answer or {}).get("value") or (clarify_answer or {}).get("text") or "").strip()
    if not value:
        return intent_spec

    # 时间窗：形如 2026-06-16~2026-06-18
    m = _DATE_RANGE_RE.search(value)
    if m:
        intent_spec["time_range"] = {"start": m.group(1), "end": m.group(2)}
        return intent_spec

    # 指标：对 L1 口径 key / name / alias 精确命中则直接落槽
    try:
        resources = get_resources(config)
        l1 = (resources.l1() or {}) if resources is not None else {}
    except Exception:
        l1 = {}
    for metric in l1.get("metrics") or []:
        names = {str(metric.get("key") or ""), str(metric.get("name") or "")}
        names.update(str(a) for a in (metric.get("aliases") or []))
        names.discard("")
        if value in names:
            intent_spec["metrics"] = [str(metric.get("name") or metric.get("key"))]
            return intent_spec

    return intent_spec


def _prev_answer_spec(history: list) -> dict:
    """最近一轮 answer 的 query_spec（历史继承来源；history 只带槽位摘要，见 SDD §3.1 / §9.1）。"""
    for entry in reversed(history or []):
        if entry.get("role") != "assistant":
            continue
        spec = entry.get("query_spec")
        if isinstance(spec, dict) and spec:
            return spec
    return {}


def _history_summary(history: list) -> str:
    """压缩最近几轮为「用户问 / 已确认槽位」文本，供 S1 判断是否为追问；不含 rows。"""
    lines = []
    for entry in (history or [])[-6:]:
        if entry.get("role") == "user":
            content = str(entry.get("content") or "").strip()
            if content:
                lines.append(f"用户问：{content}")
        elif entry.get("role") == "assistant":
            spec = entry.get("query_spec")
            if not isinstance(spec, dict) or not spec:
                continue
            summary = {
                k: spec.get(k)
                for k in ("metrics", "dimensions", "filters", "time_range", "comparison")
                if spec.get(k) not in (None, [], {})
            }
            if summary:
                lines.append(f"已确认槽位：{json.dumps(summary, ensure_ascii=False)}")
    return "\n".join(lines)


def _merge_history_slots(intent_spec: dict, history: list, llm_inherit, inherited: dict) -> None:
    """历史继承：LLM 只判定要不要继承（inherited 槽位名），值从上一轮 query_spec 确定性复制（SDD §3.1）。"""
    if isinstance(llm_inherit, dict):
        llm_inherit = [k for k, v in llm_inherit.items() if v]
    if not isinstance(llm_inherit, list):
        return
    prev_spec = _prev_answer_spec(history)
    if not prev_spec:
        return
    for slot in ("time_range", "dimensions", "filters"):
        if slot not in llm_inherit:
            continue
        if intent_spec.get(slot) not in (None, [], {}):
            continue  # 当前问题已显式给出，不覆盖
        if prev_spec.get(slot) in (None, [], {}):
            continue  # 上一轮也没有，保持缺失走澄清
        intent_spec[slot] = prev_spec[slot]
        inherited[slot] = prev_spec[slot]


def understand(state, config) -> dict:
    question = state.get("question", "")
    trace = add_trace(state, "understand", "S1 理解")
    clarify_answer = state.get("clarify_answer") or {}
    history = state.get("history") or []

    # 三类范围问题硬拦截（关键词）
    scope_code = _check_scope(question)
    if scope_code is not None:
        return _business_reject(state, scope_code, trace)

    # 超数据时间范围硬拦截（显式年份 vs L0 data_range）
    data_range = _get_data_range(config)
    if _check_no_data(question, data_range):
        return _business_reject(state, RejectCode.NO_DATA, trace, data_range)

    # 澄清回填：能确定性写槽的值（时间窗 / L1 口径 key·name·alias）不拼进问题再理解一遍（SDD-后端 §2.2）；
    # 只有确定性合并不了的自由文本才并入问题让 LLM 一起理解
    clarify_value = str(clarify_answer.get("value") or clarify_answer.get("text") or "").strip()
    llm_question = question
    if clarify_value and not _can_merge_deterministically(clarify_value, config):
        llm_question = f"{question}（用户补充：{clarify_value}）"

    # 调 Planner·理解抽意图（temperature=0）
    history_text = _history_summary(history)
    system_prompt = (
        "你是 ChatBI 的 Planner·理解（S1）。把问题翻译成结构化意图，只输出 JSON，"
        "字段：metrics/dimensions/filters/time_range/comparison/inherited。不判断能不能答。"
        "inherited 是字符串数组：当当前问题是对上一轮的追问（如「那…呢？」），其中未提及、"
        "需要从上一轮继承的槽位名（只能取 time_range/dimensions/filters），追问时必须列出，"
        "不要把上一轮的值复述进当前槽位（值由规则复制，不由你填写）；独立完整的问题输出空数组。"
        "指标与对比不继承，始终以当前问题为准。"
    )
    user_content = llm_question
    if history_text:
        user_content = f"最近对话：\n{history_text}\n当前问题：{llm_question}"
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    intent_spec = llm.chat_json(settings.model_small, messages, temperature=0)

    # 意图非法 → 重试 1 次
    if not intent_spec or not isinstance(intent_spec, dict):
        intent_spec = llm.chat_json(settings.model_small, messages, temperature=0)
        if not intent_spec or not isinstance(intent_spec, dict):
            return {
                **state,
                "action": "reject",
                "reject": {
                    "reason_code": RejectCode.INTENT_PARSE_FAILED.value,
                    "message": "无法理解该问题",
                    "suggestions": [{"label": "换个问法", "question": "请尝试更具体的提问，例如：昨天的GMV是多少？"}],
                    "retryable": True,
                },
                "trace": trace,
            }

    # 兜底：确保五类槽位存在
    intent_spec.setdefault("metrics", [])
    intent_spec.setdefault("dimensions", [])
    intent_spec.setdefault("filters", [])
    intent_spec.setdefault("time_range", None)
    intent_spec.setdefault("comparison", None)

    # 澄清回填：确定性槽位合并
    if clarify_answer:
        intent_spec = _merge_clarify_answer(intent_spec, clarify_answer, config)

    # 回填内容进 inherited：S2 缓存键靠它区分「裸问」与「已带槽位」（SDD §7.2 / §7.5）
    inherited = {"clarify": clarify_value} if clarify_value else {}

    # 历史继承：LLM 判定要继承的槽位名，值从上一轮 answer 的 query_spec 确定性复制（SDD §3.1）
    llm_inherit = intent_spec.pop("inherited", [])
    _merge_history_slots(intent_spec, history, llm_inherit, inherited)

    return {
        **state,
        "intent_spec": intent_spec,
        "inherited": inherited,
        "trace": trace,
    }
