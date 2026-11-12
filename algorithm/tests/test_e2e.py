"""端到端测试：完整链路。"""
from algorithm import llm
from algorithm.nodes.template import _make_cache_key
from algorithm.run import ask


def test_zero_resource_answer(zero_resources, mock_runner, cache_store):
    """零增强包（仅 L0）下完整链路返回 answer，degraded=true。"""
    llm.set_mock_responses({
        "understand": {"metrics": ["GMV"], "dimensions": [], "filters": [], "time_range": {"start": "2026-11-01", "end": "2026-11-11"}, "comparison": None},
        "plan": {"tables": ["dwd_order"], "metrics": [{"name": "gmv", "formula": "SUM(pay_amount)"}], "dimensions": [], "filters": [], "time_range": {"start": "2026-11-01", "end": "2026-11-11"}, "comparison": None, "degraded": True, "reachable": "answer"},
        "coder": "SELECT SUM(pay_amount) AS gmv FROM dwd_order WHERE order_date >= '2026-11-01' AND order_date < '2026-11-12'",
        "writer": "本期GMV为12345.67元。",
    })
    result = ask("2026年11月的GMV是多少", session_id="s1", runner=mock_runner, cache_store=cache_store, resources=zero_resources)
    assert result["action"] == "answer"
    assert result["result"] is not None
    assert result["result"]["rows"]  # 非空
    assert result["clarify"] is None
    assert result["reject"] is None


def test_template_hit_skips_s3_s5(mock_resources, mock_runner, cache_store):
    """模板命中时跳过 retrieve/plan/gen_sql。"""
    from algorithm.protocols import MockResourceProvider
    tpl = {
        "required_slots": ["metrics", "time_range"],
        "metric_columns": {"GMV": "pay_amount"},
        "sql_template": "SELECT SUM({metric_col}) AS v FROM dwd_order WHERE order_date >= '{start_date}' AND order_date < '{end_date}'",
    }
    res = MockResourceProvider(
        l0=mock_resources._l0,
        templates=[tpl],
    )
    llm.set_mock_responses({
        "understand": {"metrics": ["GMV"], "dimensions": [], "filters": [], "time_range": {"start": "2026-11-01", "end": "2026-11-12"}, "comparison": None},
        "writer": "本期GMV为12345.67元。",
    })
    result = ask("昨天的GMV", session_id="s2", runner=mock_runner, cache_store=cache_store, resources=res)
    assert result["action"] == "answer"
    nodes = [t["node"] for t in result["trace"]]
    assert "retrieve" not in nodes
    assert "plan" not in nodes
    assert "gen_sql" not in nodes


def test_write_op_rejected(mock_resources, mock_runner, cache_store):
    result = ask("把GMV改成0", session_id="s3", runner=mock_runner, cache_store=cache_store, resources=mock_resources)
    assert result["action"] == "reject"
    assert result["reject"]["reason_code"] == "write_op"
    assert result["reject"]["retryable"] is False


def test_clarify_flow(mock_resources, mock_runner, cache_store):
    llm.set_mock_responses({
        "understand": {"metrics": ["GMV"], "dimensions": [], "filters": [], "time_range": None, "comparison": None},
        "plan": {"tables": ["dwd_order"], "metrics": [], "dimensions": [], "filters": [], "time_range": None, "comparison": None, "degraded": False, "reachable": "clarify", "ambiguity": [{"dimension": "时间", "options": ["本周", "本月"]}], "missing": ["time_range"]},
    })
    result = ask("GMV怎么样", session_id="s4", runner=mock_runner, cache_store=cache_store, resources=mock_resources)
    assert result["action"] == "clarify"
    assert result["clarify"] is not None
    assert result["result"] is None


def test_clarified_answer_cache_not_shared_with_bare_question(mock_resources, mock_runner, cache_store):
    """澄清回填后答出的问句写缓存；同一裸问句再问不得命中（SDD §7.5：key 含 inherited）。"""
    llm.set_mock_responses({
        "understand": {"metrics": ["转化率"], "dimensions": [], "filters": [], "time_range": None, "comparison": None},
        "plan": {"tables": ["dwd_order"], "metrics": [{"name": "转化率", "formula": "SUM(pay_amount)"}], "dimensions": [], "filters": [], "time_range": None, "comparison": None, "degraded": False, "reachable": "answer"},
        "coder": "SELECT SUM(pay_amount) AS v FROM dwd_order WHERE order_date >= '2026-06-16' AND order_date < '2026-06-19'",
        "writer": "转化率已查出。",
    })
    # 第一次：带澄清回填（时间窗）→ answer 并写缓存
    first = ask("看一下转化率", session_id="s6", clarify_answer={"value": "2026-06-16~2026-06-18"},
                runner=mock_runner, cache_store=cache_store, resources=mock_resources)
    assert first["action"] == "answer"
    assert len(cache_store.put_calls) == 1
    # 写入键必须带 inherited，不等于裸问句键
    bare_key = _make_cache_key("看一下转化率", {}, "||v1")
    assert cache_store.put_calls[0][0] != bare_key

    # 第二次：裸问句 → 缓存不命中，缺时间窗 → 重新走 clarify
    second = ask("看一下转化率", session_id="s7",
                 runner=mock_runner, cache_store=cache_store, resources=mock_resources)
    assert second["action"] == "clarify"
    assert len(cache_store.put_calls) == 1  # 澄清不写缓存


def test_compare_two_periods(mock_resources, mock_runner, cache_store):
    """同比问题 → 两行对比表 + bar + x_field=period。"""
    llm.set_mock_responses({
        "understand": {"metrics": ["GMV"], "dimensions": [], "filters": [], "time_range": {"start": "2026-11-01", "end": "2026-11-11"}, "comparison": {"type": "yoy", "baseline": "2025-11-01~2025-11-11"}},
        "plan": {"tables": ["dwd_order"], "metrics": [{"name": "gmv", "formula": "SUM(pay_amount)"}], "dimensions": [], "filters": [], "time_range": {"start": "2026-11-01", "end": "2026-11-11"}, "comparison": {"type": "yoy"}, "degraded": False, "reachable": "answer"},
        "coder": "SELECT '本期' AS period, SUM(pay_amount) AS gmv FROM dwd_order UNION ALL SELECT '同期' AS period, SUM(pay_amount) AS gmv FROM dwd_order",
        "writer": "本期GMV同比增长23.5%。",
    })
    result = ask("双11GMV同比", session_id="s5", runner=mock_runner, cache_store=cache_store, resources=mock_resources)
    assert result["action"] == "answer"
    chart = result["result"]["chart"]
    assert chart["type"] == "bar"
    assert chart["x_field"] == "period"
    assert len(result["result"]["rows"]) == 2
