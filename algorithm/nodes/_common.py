"""节点共享工具：从 LangGraph config 取注入的 runner / cache_store / resources。"""
import time
from typing import Any

from ..exceptions import RejectCode
from ..protocols import CacheStore, QueryRunner, ResourceProvider

# 业务类拒答文案模板（SDD §5.3：模板写死，不经模型自由生成；拒答响应不得包含计算得出的数字）
REJECT_TEMPLATES = {
    RejectCode.WRITE_OP: {
        "message": "我只能查数，不能改数：系统对数据库是只读的，不接受任何写入、修改或删除请求。",
        "suggestions": [{"label": "查看原值", "question": "2026年618大促期的GMV是多少？"}],
    },
    RejectCode.DETAIL_EXPORT: {
        "message": "我不能导出订单明细，只能回答汇总后的指标。",
        "suggestions": [{"label": "看每日汇总", "question": "2026年618大促期每天的GMV是多少？"}],
    },
    RejectCode.OUT_OF_SCOPE: {
        "message": "系统里只有本平台的经营数据，没有竞品或外部数据，这个查不了。",
        "suggestions": [{"label": "看本品渠道结构", "question": "2026年618大促期分渠道的GMV是多少？"}],
    },
    RejectCode.NO_DATA: {
        "message": "数据范围是 {data_min} ~ {data_max}，你要查的时间不在这个范围内，没有数据可算。",
        "suggestions": [{"label": "查最新档期", "question": "2026年618大促期的GMV是多少？"}],
    },
}


def business_reject_payload(code: RejectCode, data_range: dict | None = None) -> dict:
    """四类业务拒答的 payload：文案全部来自 REJECT_TEMPLATES（SDD §5.3 铁律）。"""
    tpl = REJECT_TEMPLATES[code]
    message = tpl["message"]
    if code is RejectCode.NO_DATA and data_range:
        message = message.format(
            data_min=data_range.get("min_date", "?"),
            data_max=data_range.get("max_date", "?"),
        )
    return {
        "reason_code": code.value,
        "message": message,
        "suggestions": [dict(s) for s in tpl["suggestions"]],
        "retryable": False,
    }


def get_runner(config: dict) -> QueryRunner:
    return config["configurable"]["runner"]


def get_cache_store(config: dict) -> CacheStore:
    return config["configurable"]["cache_store"]


def get_resources(config: dict) -> ResourceProvider:
    return config["configurable"]["resources"]


def get_max_rows(config: dict) -> int:
    return config["configurable"].get("max_rows", 1000)


def get_timeout_ms(config: dict) -> int:
    return config["configurable"].get("timeout_ms", 5000)


def add_trace(state: dict, node: str, note: str = "", extra: dict | None = None) -> list[dict]:
    trace = list(state.get("trace") or [])
    item: dict = {"node": node, "note": note, "ts": round(time.time(), 3)}
    if extra:
        item.update(extra)
    trace.append(item)
    return trace

