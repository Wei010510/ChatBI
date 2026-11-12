"""测试夹具：Mock LLM、Mock runner/cache/resources。"""
import pytest

from algorithm import llm
from algorithm.protocols import MockQueryRunner, MemoryCacheStore, MockResourceProvider


@pytest.fixture(autouse=True)
def use_mock_llm():
    """默认启用 MockLLM（settings.use_mock_llm 默认为 true），每个测试可通过 set_mock_responses 配置。"""
    llm.set_mock_responses({})
    yield
    llm.set_mock_responses({})


@pytest.fixture
def l0_data():
    return {
        "tables": [{"name": "dwd_order"}, {"name": "dim_date"}],
        "columns": [
            {"name": "pay_amount", "comment": "支付金额", "type": "number", "table": "dwd_order"},
            {"name": "order_status", "comment": "订单状态", "type": "string", "table": "dwd_order"},
            {"name": "order_date", "comment": "订单日期", "type": "date", "table": "dwd_order"},
            {"name": "dt", "comment": "日期", "type": "date", "table": "dim_date"},
        ],
        "data_range": {"min_date": "2024-01-01", "max_date": "2026-11-11"},
        "schema_version": "v1",
    }


@pytest.fixture
def mock_resources(l0_data):
    return MockResourceProvider(
        l0=l0_data,
        l1={
            "metrics": [
                {"key": "gmv", "name": "GMV", "aliases": ["成交额"], "formula": "SUM(pay_amount)", "ambiguity": []},
            ],
            "dimensions": [
                {"key": "channel", "name": "渠道", "aliases": ["渠道"], "column": "dwd_payment.channel_code"},
            ],
        },
        templates=[],
        exemplars=[],
        aliases={},
    )


@pytest.fixture
def zero_resources(l0_data):
    """零增强包：只有 L0。"""
    return MockResourceProvider(l0=l0_data)


@pytest.fixture
def mock_runner():
    return MockQueryRunner(
        columns=[
            {"key": "period", "title": "period", "type": "string"},
            {"key": "gmv", "title": "gmv", "type": "number"},
        ],
        rows=[{"period": "本期", "gmv": 12345.67}, {"period": "同期", "gmv": 10000.0}],
    )


@pytest.fixture
def cache_store():
    return MemoryCacheStore()
