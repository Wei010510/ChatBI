"""S2 模板快道：纯规则，槽位比骨架，命中填空跳 S6，未命中继续 S3。"""
import hashlib
import json
import re
from datetime import date, timedelta

from ._common import add_trace, get_resources, get_cache_store

_DEFAULT_LIMIT = 10
_CN_LIMITS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _norm(value) -> str:
    return str(value).strip().lower()


def _make_cache_key(question: str, inherited: dict | None = None, template_version: str = "") -> str:
    """SDD §7.5：key 含 inherited（澄清回填槽位），裸问句与澄清后问句不共享缓存。"""
    inherited_json = json.dumps(inherited or {}, sort_keys=True, ensure_ascii=False)
    payload = f"{question.strip()}|{inherited_json}|{template_version}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _template_version(resources) -> str:
    """模板文件版本；取不到时用空串，缓存键机制不变。"""
    fn = getattr(resources, "template_version", None)
    if not callable(fn):
        return ""
    try:
        return str(fn() or "")
    except Exception:
        return ""


def _metric_col(tpl: dict, metric: str) -> str | None:
    cols = tpl.get("metric_columns") or {}
    if not isinstance(cols, dict):
        return None
    target = _norm(metric)
    for key, value in cols.items():
        if _norm(key) == target and value:
            return str(value)
    return None


def _resolve_dim_key(value, l1: dict) -> str:
    """把意图里的维度说法归一为 L1 的维度 key。"""
    target = _norm(value)
    dims = (l1.get("dimensions") or []) if isinstance(l1, dict) else []
    for dim in dims:
        if not isinstance(dim, dict):
            continue
        terms = [dim.get("key") or "", dim.get("name") or ""]
        terms += [str(a) for a in (dim.get("aliases") or [])]
        if target in {_norm(t) for t in terms if t}:
            return _norm(dim.get("key"))
    return target


def _parse_date(value) -> date | None:
    if value is None:
        return None
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _time_range(intent_spec: dict) -> tuple[date | None, date | None]:
    tr = intent_spec.get("time_range") or {}
    if not isinstance(tr, dict):
        return None, None
    start = _parse_date(tr.get("start") or tr.get("start_date") or tr.get("from"))
    end = _parse_date(tr.get("end") or tr.get("end_date") or tr.get("to"))
    if not start or not end or start > end:
        return None, None
    return start, end


def _prev_yoy(start: date, end: date) -> tuple[date, date]:
    try:
        return start.replace(year=start.year - 1), end.replace(year=end.year - 1)
    except ValueError:  # 2/29 跨年
        return start.replace(year=start.year - 1, day=28), end.replace(year=end.year - 1, day=28)


def _prev_period(start: date, end: date) -> tuple[date, date]:
    days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    return prev_end - timedelta(days=days - 1), prev_end


def _extract_limit(question: str) -> int:
    text = question.lower()
    match = re.search(r"(?:top|前)\s*(\d{1,3})", text)
    if match:
        n = int(match.group(1))
        if 1 <= n <= 100:
            return n
    match = re.search(r"前\s*([一二三四五六七八九十])", text)
    if match:
        return _CN_LIMITS[match.group(1)]
    return _DEFAULT_LIMIT


def _comparison_kind(intent_spec: dict, question: str) -> str:
    comp = intent_spec.get("comparison")
    kind = ""
    if isinstance(comp, dict):
        kind = _norm(comp.get("type") or comp.get("key") or "")
    elif comp:
        kind = _norm(comp)
    if kind in {"yoy", "同比"}:
        return "yoy"
    if kind in {"mom", "wow", "环比", "上期"}:
        return "mom"
    text = _norm(question)
    if any(k in text for k in ("同比", "去年同期", "yoy")):
        return "yoy"
    if any(k in text for k in ("环比", "上一周期", "上期", "上周", "上月", "mom", "wow")):
        return "mom"
    return ""


def _keyword_hits(keyword: str, question: str) -> bool:
    """“前”必须跟数量才算 TopN，避免“当前 / 目前”误命中。"""
    if keyword == "前":
        return bool(re.search(r"前\s*(?:\d{1,3}|[一二三四五六七八九十])", question))
    return keyword in question


def _shape_ok(tpl: dict, intent_spec: dict, l1: dict, question: str) -> bool:
    """槽位齐全 / 能落列 / 口径无歧义；多出来的槽位不静默丢弃。"""
    metrics = intent_spec.get("metrics") or []
    time_range = intent_spec.get("time_range")
    dimensions = intent_spec.get("dimensions") or []
    filters = intent_spec.get("filters") or []
    comparison = intent_spec.get("comparison")

    # 模板只覆盖单指标
    if len(metrics) != 1:
        return False

    required = [s for s in (tpl.get("required_slots") or []) if isinstance(s, str)]
    if "metrics" not in required:
        return False
    if "time_range" in required and not time_range:
        return False
    if "dimensions" in required and not dimensions:
        return False
    if "comparison" in required and not comparison:
        return False

    # 模板 SQL 不渲染过滤条件，有 filters 时不命中
    if filters:
        return False

    if dimensions:
        if "dimensions" not in required or len(dimensions) != 1:
            return False
        supported = {_norm(k) for k in (tpl.get("dimension_columns") or {})}
        if not supported:
            return False
        if _resolve_dim_key(dimensions[0], l1) not in supported:
            return False

    if comparison:
        if "comparison" not in required:
            return False
        if not _comparison_kind(intent_spec, question):
            return False

    keywords = [_norm(k) for k in (tpl.get("trigger_keywords") or []) if k]
    if keywords and not any(_keyword_hits(k, _norm(question)) for k in keywords):
        return False

    return _metric_col(tpl, metrics[0]) is not None


def _fill_sql(tpl: dict, intent_spec: dict, question: str) -> str | None:
    sql = str(tpl.get("sql_template") or "")
    if not sql:
        return None

    start, end = _time_range(intent_spec)
    if ("{start_date}" in sql or "{end_date}" in sql) and (start is None or end is None):
        return None

    metrics = intent_spec.get("metrics") or []
    col = _metric_col(tpl, metrics[0]) if metrics else None
    if "{metric_col}" in sql and not col:
        return None

    replacements = {
        "{start_date}": start.isoformat() if start else "",
        "{end_date}": end.isoformat() if end else "",
        "{metric_col}": col or "",
        "{limit}": str(_extract_limit(question)),
    }

    if "{prev_start_date}" in sql or "{prev_end_date}" in sql:
        if start is None or end is None:
            return None
        kind = _comparison_kind(intent_spec, question)
        if kind == "yoy":
            prev_start, prev_end = _prev_yoy(start, end)
        elif kind == "mom":
            prev_start, prev_end = _prev_period(start, end)
        else:
            return None
        replacements["{prev_start_date}"] = prev_start.isoformat()
        replacements["{prev_end_date}"] = prev_end.isoformat()

    for key, value in replacements.items():
        sql = sql.replace(key, value)

    # 占位符没填干净 → 视为未命中
    if re.search(r"\{[a-zA-Z_]+\}", sql):
        return None
    return sql


def template(state, config) -> dict:
    resources = get_resources(config)
    cache_store = get_cache_store(config)
    question = state.get("question", "")
    trace = add_trace(state, "template", "S2 模板快道")

    # 精确重复：查缓存（key 掺模板 / L1 / L0 版本，任一版本变化旧键自然失效）
    l1 = resources.l1() or {}
    l1_version = str(l1.get("version") or "") if isinstance(l1, dict) else ""
    l0 = resources.l0() or {}
    schema_version = str(l0.get("schema_version") or "") if isinstance(l0, dict) else ""
    cache_key = _make_cache_key(
        question,
        state.get("inherited"),
        f"{_template_version(resources)}|{l1_version}|{schema_version}",
    )
    cached = cache_store.get(cache_key)
    if cached and cached.get("sql"):
        trace[-1]["source"] = "cache"
        return {
            **state,
            "cache_hit": True,
            "template_hit": True,
            "query_spec": cached.get("query_spec"),
            "sql": cached["sql"],
            "chart_spec": cached.get("chart_spec"),
            "cache_key": cache_key,
            "trace": trace,
        }

    # 模板匹配
    intent_spec = state.get("intent_spec", {}) or {}
    templates = resources.templates() or []

    matched = None
    sql = None
    for tpl in templates:
        if not isinstance(tpl, dict) or not _shape_ok(tpl, intent_spec, l1, question):
            continue
        candidate = _fill_sql(tpl, intent_spec, question)
        if candidate:
            matched, sql = tpl, candidate
            break

    if matched:
        metrics = intent_spec.get("metrics") or []
        query_spec = {
            "metrics": metrics,
            "dimensions": intent_spec.get("dimensions") or [],
            "filters": intent_spec.get("filters") or [],
            "time_range": intent_spec.get("time_range"),
            "comparison": intent_spec.get("comparison"),
        }
        trace[-1]["template_id"] = matched.get("id")
        trace[-1]["source"] = "template"
        return {
            **state,
            "template_hit": True,
            "query_spec": query_spec,
            "sql": sql,
            "cache_key": cache_key,
            "trace": trace,
        }

    # 未命中：继续 S3
    trace[-1]["template_id"] = None
    return {
        **state,
        "template_hit": False,
        "cache_hit": False,
        "cache_key": cache_key,
        "trace": trace,
    }
