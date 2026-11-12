"""S1 理解节点测试。"""
from algorithm.nodes.understand import understand


def _config():
    return {"configurable": {"runner": None, "cache_store": None, "resources": None, "max_rows": 1000, "timeout_ms": 5000}}


def test_normal_question_produces_intent():
    from algorithm import llm
    llm.set_mock_responses({"understand": {"metrics": ["GMV"], "dimensions": [], "filters": [], "time_range": {"start": "2026-11-01", "end": "2026-11-11"}, "comparison": None}})
    state = {"question": "这次双11的GMV是多少", "trace": []}
    out = understand(state, _config())
    assert out["intent_spec"]["metrics"] == ["GMV"]
    assert "action" not in out  # 不做判断


def test_write_op_rejected():
    state = {"question": "把GMV改成0", "trace": []}
    out = understand(state, _config())
    assert out["action"] == "reject"
    assert out["reject"]["reason_code"] == "write_op"


def test_detail_export_rejected():
    state = {"question": "导出所有订单明细", "trace": []}
    out = understand(state, _config())
    assert out["action"] == "reject"
    assert out["reject"]["reason_code"] == "detail_export"


_PREV_SPEC = {
    "metrics": ["GMV"],
    "dimensions": ["渠道"],
    "filters": [],
    "time_range": {"start": "2026-06-16", "end": "2026-06-18"},
    "comparison": None,
}

_HISTORY = [
    {"role": "user", "content": "大促期各渠道的GMV是多少"},
    {"role": "assistant", "action": "answer", "query_spec": _PREV_SPEC},
]


def test_followup_inherits_slots_from_history():
    from algorithm import llm
    llm.set_mock_responses({"understand": {
        "metrics": ["转化率"], "dimensions": [], "filters": [],
        "time_range": None, "comparison": None,
        "inherited": ["time_range", "dimensions"],
    }})
    state = {"question": "那转化率呢？", "history": _HISTORY, "trace": []}
    out = understand(state, _config())
    assert out["intent_spec"]["metrics"] == ["转化率"]  # 指标不继承
    assert out["intent_spec"]["time_range"] == {"start": "2026-06-16", "end": "2026-06-18"}
    assert out["intent_spec"]["dimensions"] == ["渠道"]
    assert out["inherited"]["time_range"] == {"start": "2026-06-16", "end": "2026-06-18"}
    assert out["inherited"]["dimensions"] == ["渠道"]


def test_independent_question_does_not_inherit():
    from algorithm import llm
    llm.set_mock_responses({"understand": {
        "metrics": ["GMV"], "dimensions": [], "filters": [],
        "time_range": {"start": "2026-06-01", "end": "2026-06-30"}, "comparison": None,
        "inherited": [],
    }})
    state = {"question": "6月整体GMV是多少", "history": _HISTORY, "trace": []}
    out = understand(state, _config())
    assert out["intent_spec"]["dimensions"] == []
    assert out["inherited"] == {}


def test_inherit_flag_without_prev_spec_is_noop():
    from algorithm import llm
    llm.set_mock_responses({"understand": {
        "metrics": ["转化率"], "dimensions": [], "filters": [],
        "time_range": None, "comparison": None,
        "inherited": ["time_range"],
    }})
    state = {"question": "那转化率呢？", "history": [], "trace": []}
    out = understand(state, _config())
    assert out["intent_spec"]["time_range"] is None
    assert "time_range" not in out["inherited"]
