"""ChatState 与交接数据模型（与 SDD §7.2 / §7.3 / §7.4 一致）。"""
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class IntentSpec(TypedDict, total=False):
    """S1 产物：五类槽位。"""
    metrics: list[str]
    dimensions: list[str]
    filters: list[dict]
    time_range: dict
    comparison: dict | None


class Evidence(TypedDict, total=False):
    """S3 产物：四类弹药。"""
    tables: list[dict]
    columns: list[dict]
    metrics: list[dict]
    entities: list[dict]
    examples: list[dict]
    l1_available: bool


class Plan(TypedDict, total=False):
    """S4 产物。"""
    tables: list[str]
    metrics: list[dict]
    dimensions: list[str]
    filters: list[dict]
    time_range: dict
    comparison: dict | None
    few_shot: list[dict]
    degraded: bool
    reachable: Literal["answer", "clarify", "reject"]


class QuerySpec(BaseModel):
    """§7.3 唯一口径事实来源。"""
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[dict] = Field(default_factory=list)
    time_range: dict | None = None
    comparison: dict | None = None
    granularity: str = "total"
    order_by: dict | None = None
    limit: int | None = None


class ChartSpec(BaseModel):
    type: Literal["bar", "line"]
    x_field: str | None
    series: list[dict] = Field(default_factory=list)


class Clarify(TypedDict):
    clarify_id: str
    question: str
    options: list[dict]
    allow_free_text: bool
    missing: list[str]


class Reject(TypedDict):
    reason_code: str
    message: str
    suggestions: list[dict]
    retryable: bool


class ChainResult(TypedDict):
    """§7.4 一次问数返回体，写死。"""
    action: Literal["answer", "clarify", "reject"]
    result: dict | None
    clarify: dict | None
    reject: dict | None
    trace: list[dict]


class ChatState(TypedDict, total=False):
    """§7.2 链路状态，写死。runner/cache_store/resources 不进 state。"""
    # 输入
    session_id: str
    question: str
    history: list[dict]
    clarify_answer: dict | None

    # S1
    normalized_question: str
    intent: str
    intent_spec: dict
    inherited: dict

    # S2 / S3
    cache_key: str
    cache_hit: bool
    template_hit: bool
    cached_sql: str | None
    evidence: dict
    templates_used: list[str]

    # S4 / S5
    plan: dict
    reachable: str
    ambiguity: list[dict]
    query_spec: dict
    sql: str
    lint_ok: bool
    lint_round: int
    lint_errors: list[str]
    sql_error: str | None
    retry_count: int

    # S6
    columns: list[dict]
    rows: list[dict]
    truncated: bool
    validation: dict

    # S7 / S8
    chart_spec: dict | None
    narrative: str

    # 出口
    action: str
    result: dict | None
    clarify: dict | None
    clarify_id: str | None
    reject: dict | None
    trace: list[dict]
