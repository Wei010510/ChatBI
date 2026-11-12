"""S7 出表 + 图：列名换业务名，chart_spec 按形状查表（只出 bar/line）。"""
import re
from datetime import date, timedelta

from ._common import add_trace

_CUR_RE = re.compile(r"^(?:current|cur)_(.+)$", re.IGNORECASE)
_PREV_RE = re.compile(r"^(?:previous|prev)_(.+)$", re.IGNORECASE)
# 派生列没有业务名时按 key 兜底翻译（SDD §2.9，越具体的后缀越先匹配）
_DERIVED_TITLES = (
    ("_rate", "增长率"),
    ("_ratio", "占比"),
    ("_share", "占比"),
    ("_pct", "百分比"),
    ("growth", "增长"),
    ("yoy", "同比"),
)


def _name_of(item) -> str:
    """指标项可能是对象 {name} 或字符串，两种都兼容。"""
    if isinstance(item, dict):
        return str(item.get("name") or "")
    return str(item or "")


def _metric_names(plan_dict: dict, query_spec: dict) -> list[str]:
    """plan 优先；缓存命中时 plan 为空，用 query_spec 兜底。"""
    names = [n for n in (_name_of(m) for m in (plan_dict.get("metrics") or [])) if n]
    if not names:
        names = [n for n in (_name_of(m) for m in (query_spec.get("metrics") or [])) if n]
    return names


def _metric_title(name: str) -> str:
    """英文 snake_case 指标名取末段大写（total_gmv → GMV）；中文名原样。"""
    text = str(name or "")
    if re.fullmatch(r"[a-z][a-z0-9_]*", text):
        return text.rsplit("_", 1)[-1].upper()
    return text


def _biz_names(metric_names: list[str]) -> dict:
    """完整名与末段名都登记，列名 current_gmv / gmv 都能对上 total_gmv。"""
    names = {}
    for name in metric_names:
        title = _metric_title(name)
        names.setdefault(name.lower(), title)
        names.setdefault(name.lower().rsplit("_", 1)[-1], title)
    return names


def _l0_titles(config) -> dict:
    """L0 列注释 → 业务名兜底。取不到资源时返回空表。"""
    try:
        l0 = config["configurable"]["resources"].l0() or {}
    except Exception:
        return {}
    titles = {}
    for col in l0.get("columns") or []:
        name = str(col.get("name") or "")
        if name and col.get("comment"):
            titles[name.lower()] = str(col["comment"])
    return titles


def _title(key: str, biz_names: dict, l0_titles: dict) -> str:
    lower = key.lower()
    if lower in biz_names:
        return biz_names[lower]
    # current_gmv / previous_gmv 这类带前缀的列，按后缀对上指标名
    for name, title in biz_names.items():
        if lower.endswith(f"_{name}"):
            return title
    if lower in l0_titles:
        return l0_titles[lower]
    for token, label in _DERIVED_TITLES:
        if token in lower:
            return label
    return key


def _parse_date(value) -> date | None:
    text = str(value or "")[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _comparison_kind(query_spec: dict) -> str:
    comp = query_spec.get("comparison")
    kind = ""
    if isinstance(comp, dict):
        kind = str(comp.get("type") or comp.get("key") or "").lower()
    elif comp:
        kind = str(comp).lower()
    if any(token in kind for token in ("year", "yoy", "同比")):
        return "yoy"
    if any(token in kind for token in ("month", "week", "period", "mom", "wow", "环比")):
        return "mom"
    return ""


def _fmt_range(start: date, end: date) -> str:
    if start.year == end.year:
        return f"{start.isoformat()}~{end.strftime('%m-%d')}"
    return f"{start.isoformat()}~{end.isoformat()}"


def _window(value) -> tuple[date, date] | None:
    if not isinstance(value, dict):
        return None
    start = _parse_date(value.get("start") or value.get("start_date"))
    end = _parse_date(value.get("end") or value.get("end_date"))
    if not start or not end or start > end:
        return None
    return start, end


def _period_labels(query_spec: dict) -> tuple[str, str]:
    """本期 / 上期标签：优先用 S4 写死的两期，其次按同比 / 环比推算。"""
    comp = query_spec.get("comparison") if isinstance(query_spec.get("comparison"), dict) else {}
    tr = query_spec.get("time_range") or {}
    current = _window(comp.get("current_period")) or (_window(tr) if isinstance(tr, dict) else None)
    if not current:
        return "本期", "上期"
    previous = _window(comp.get("previous_period"))
    if not previous:
        start, end = current
        kind = _comparison_kind(query_spec)
        if kind == "yoy":
            try:
                previous = (start.replace(year=start.year - 1), end.replace(year=end.year - 1))
            except ValueError:  # 2/29
                previous = (start.replace(year=start.year - 1, day=28), end.replace(year=end.year - 1, day=28))
        elif kind == "mom":
            days = (end - start).days + 1
            prev_end = start - timedelta(days=1)
            previous = (prev_end - timedelta(days=days - 1), prev_end)
    if not previous:
        return _fmt_range(*current), "上期"
    return _fmt_range(*current), _fmt_range(*previous)


def _normalize_comparison(columns: list[dict], rows: list[dict], query_spec: dict, metric_names: list[str]):
    """把 wide 表（1 行）摊平成两行 period 表：current_* / previous_* 或 v / prev_v（SDD §2.9）。"""
    if len(rows) != 1 or not query_spec.get("comparison"):
        return columns, rows

    by_key = {str(c.get("key") or ""): c for c in columns}
    cur, prev = {}, {}
    for col in columns:
        key = str(col.get("key") or "")
        matched = _PREV_RE.match(key)
        if matched:
            prev[matched.group(1)] = col
            continue
        matched = _CUR_RE.match(key)
        if matched:
            cur[matched.group(1)] = col

    # v / prev_v 这种无前缀写法：prev_x 存在时，同名的 x 就是本期列
    for base in prev:
        if base not in cur and base in by_key:
            cur[base] = by_key[base]

    pairs = [(base, col) for base, col in cur.items() if base in prev]
    if not pairs:
        return columns, rows

    row = rows[0]
    kind = _comparison_kind(query_spec)
    fallback_title = _metric_title(metric_names[0]) if metric_names else ""
    period_text = str(row.get("period") or "").strip()
    if period_text:
        cur_label = period_text
        prev_label = "去年同期" if kind == "yoy" else ("上一周期" if kind == "mom" else "上期")
    else:
        cur_label, prev_label = _period_labels(query_spec)

    out_columns = [{"key": "period", "title": "周期", "type": "string"}]
    cur_row: dict = {"period": cur_label}
    prev_row: dict = {"period": prev_label}
    used_keys = {"period"}

    for base, col in pairs:
        title = str(col.get("title") or base)
        if title == base and fallback_title:
            title = fallback_title
        out_columns.append({"key": base, "title": title, "type": col.get("type", "number")})
        cur_row[base] = row.get(col["key"])
        prev_row[base] = row.get(prev[base]["key"])
        used_keys.add(col["key"])
        used_keys.add(prev[base]["key"])

    # 不成对的派生列（如 yoy / growth_rate）只填在本期那一行
    for col in columns:
        key = str(col.get("key") or "")
        if not key or key in used_keys:
            continue
        out_columns.append(col)
        cur_row[key] = row.get(key)
        prev_row[key] = None

    return out_columns, [cur_row, prev_row]


def _series(columns: list[dict], key: str) -> list[dict]:
    """系列名用业务名，图例/提示里不出现 gmv 这种机器名。"""
    title = next((c.get("title") for c in columns if c.get("key") == key), key)
    return [{"key": key, "name": title}]


def _detect_shape(columns: list[dict], rows: list[dict]) -> str:
    """判定结果形状，命中即停（SDD §2.9）。"""
    if not rows:
        return "empty"
    col_keys = [c.get("key") for c in columns]
    # 两期对比：含 period 列且 2 行
    if "period" in col_keys and len(rows) == 2:
        return "compare_two_periods"
    # 时间序列：含日期类列且 > 2 行
    date_cols = [c for c in columns if c.get("type") == "date"]
    if date_cols and len(rows) > 2:
        return "time_series"
    # 类别维度（含排名）：有维度列 + 数值列
    num_cols = [c for c in columns if c.get("type") == "number"]
    dim_cols = [c for c in columns if c.get("type") == "string"]
    if dim_cols and num_cols:
        return "category"
    return "single_scalar"


def present(state, config) -> dict:
    trace = add_trace(state, "present", "S7 出表出图")

    columns = state.get("columns", [])
    rows = state.get("rows", [])
    plan_dict = state.get("plan", {}) or {}
    query_spec = state.get("query_spec", {}) or {}
    chart_spec = None
    warnings: list[str] = []

    metric_names = _metric_names(plan_dict, query_spec)
    biz_names = _biz_names(metric_names)
    l0_titles = _l0_titles(config)
    out_columns = [
        {
            "key": c.get("key", ""),
            "title": _title(c.get("key", ""), biz_names, l0_titles),
            "type": c.get("type", "string"),
        }
        for c in columns
    ]

    out_columns, rows = _normalize_comparison(out_columns, rows, query_spec, metric_names)
    shape = _detect_shape(out_columns, rows)

    num_col = next((c["key"] for c in out_columns if c["type"] == "number"), None)

    if shape == "empty":
        chart_spec = None
    elif shape == "compare_two_periods":
        chart_spec = {"type": "bar", "x_field": "period", "series": _series(out_columns, num_col)} if num_col else None
    elif shape == "time_series":
        date_col = next((c["key"] for c in out_columns if c["type"] == "date"), None)
        chart_spec = {"type": "line", "x_field": date_col, "series": _series(out_columns, num_col)} if date_col and num_col else None
    elif shape == "category":
        dim_col = next((c["key"] for c in out_columns if c["type"] == "string"), None)
        chart_spec = {"type": "bar", "x_field": dim_col, "series": _series(out_columns, num_col)} if dim_col and num_col else None
    elif num_col:  # 单标量：固定类目「当前值」的柱状图
        chart_spec = {"type": "bar", "x_field": None, "series": _series(out_columns, num_col)}

    return {
        **state,
        "columns": out_columns,
        "rows": rows,
        "chart_spec": chart_spec,
        "validation": {"warnings": warnings},
        "trace": trace,
    }
