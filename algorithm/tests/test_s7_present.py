"""S7 出表出图节点测试。"""
from algorithm.nodes.present import present


def _config():
    return {"configurable": {}}


def test_empty_result_chart_null():
    state = {"columns": [], "rows": [], "plan": {}, "trace": []}
    out = present(state, _config())
    assert out["chart_spec"] is None


def test_two_period_bar():
    cols = [
        {"key": "period", "title": "period", "type": "string"},
        {"key": "gmv", "title": "gmv", "type": "number"},
    ]
    rows = [{"period": "本期", "gmv": 100}, {"period": "同期", "gmv": 80}]
    state = {"columns": cols, "rows": rows, "plan": {}, "trace": []}
    out = present(state, _config())
    assert out["chart_spec"]["type"] == "bar"
    assert out["chart_spec"]["x_field"] == "period"


def test_single_scalar_bar_null_x():
    cols = [{"key": "gmv", "title": "gmv", "type": "number"}]
    rows = [{"gmv": 100}]
    state = {"columns": cols, "rows": rows, "plan": {}, "trace": []}
    out = present(state, _config())
    assert out["chart_spec"]["type"] == "bar"
    assert out["chart_spec"]["x_field"] is None


def test_time_series_line():
    cols = [
        {"key": "dt", "title": "dt", "type": "date"},
        {"key": "gmv", "title": "gmv", "type": "number"},
    ]
    rows = [{"dt": "2026-01-01", "gmv": 10}, {"dt": "2026-01-02", "gmv": 20}, {"dt": "2026-01-03", "gmv": 30}]
    state = {"columns": cols, "rows": rows, "plan": {}, "trace": []}
    out = present(state, _config())
    assert out["chart_spec"]["type"] == "line"
    assert out["chart_spec"]["x_field"] == "dt"


def test_category_bar():
    cols = [
        {"key": "region", "title": "region", "type": "string"},
        {"key": "gmv", "title": "gmv", "type": "number"},
    ]
    rows = [{"region": "华东", "gmv": 100}, {"region": "华北", "gmv": 80}]
    state = {"columns": cols, "rows": rows, "plan": {}, "trace": []}
    out = present(state, _config())
    assert out["chart_spec"]["type"] == "bar"
    assert out["chart_spec"]["x_field"] == "region"


def test_derived_pct_column_title():
    """派生列 *_pct 兜底翻译为「百分比」，不显示英文原 key（SDD §2.9）。"""
    cols = [{"key": "pay_conversion_pct", "title": "pay_conversion_pct", "type": "number"}]
    rows = [{"pay_conversion_pct": 0.32}]
    state = {"columns": cols, "rows": rows, "plan": {}, "trace": []}
    out = present(state, _config())
    assert out["columns"][0]["title"] == "百分比"


def test_wide_compare_current_previous_to_two_rows():
    cols = [
        {"key": "current_gmv", "title": "current_gmv", "type": "number"},
        {"key": "previous_gmv", "title": "previous_gmv", "type": "number"},
        {"key": "growth_rate", "title": "增长", "type": "number"},
    ]
    rows = [{"current_gmv": 100, "previous_gmv": 80, "growth_rate": 0.25}]
    query_spec = {
        "comparison": {"type": "year_over_year"},
        "metrics": [{"name": "total_gmv"}],
        "time_range": {"start": "2026-06-16", "end": "2026-06-18"},
    }
    out = present({"columns": cols, "rows": rows, "plan": {}, "query_spec": query_spec, "trace": []}, _config())
    assert len(out["rows"]) == 2
    assert out["rows"][0]["period"] == "2026-06-16~06-18"
    assert out["rows"][1]["period"] == "2025-06-16~06-18"
    assert out["columns"][1]["title"] == "GMV"
    assert out["chart_spec"]["x_field"] == "period"


def test_wide_compare_v_prev_v_to_two_rows():
    cols = [
        {"key": "period", "title": "period", "type": "string"},
        {"key": "v", "title": "v", "type": "number"},
        {"key": "prev_v", "title": "prev_v", "type": "number"},
        {"key": "yoy", "title": "同比", "type": "number"},
    ]
    rows = [{"period": "本期", "v": 100, "prev_v": 80, "yoy": 0.25}]
    query_spec = {"comparison": {"type": "year_over_year"}, "metrics": [{"name": "total_gmv"}]}
    out = present({"columns": cols, "rows": rows, "plan": {}, "query_spec": query_spec, "trace": []}, _config())
    assert len(out["rows"]) == 2
    assert out["rows"][0]["period"] == "本期"
    assert out["rows"][1]["period"] == "去年同期"
    assert out["rows"][1]["v"] == 80
    assert out["columns"][1]["title"] == "GMV"
    assert out["chart_spec"]["x_field"] == "period"
