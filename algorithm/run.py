"""算法入口：组装依赖、调用图、返回 ChainResult（SDD §7.4 / §9.4）。"""
from typing import Any

from .graph import build_graph
from .protocols import CacheStore, QueryRunner, ResourceProvider
from .state import ChatState, ChainResult


def ask(
    question: str,
    *,
    session_id: str = "",
    history: list[dict] | None = None,
    clarify_answer: dict | None = None,
    runner: QueryRunner,
    cache_store: CacheStore,
    resources: ResourceProvider,
    max_rows: int = 1000,
    timeout_ms: int = 5000,
) -> ChainResult:
    """一次问数入口。

    runner / cache_store / resources 由调用方（后端）注入，算法不持数据库连接。
    clarify_answer 为澄清回填（结构化补全，SDD §2.2），由 S1 读取并确定性落槽。
    """
    graph = build_graph()

    initial_state: ChatState = {
        "session_id": session_id,
        "question": question,
        "history": history or [],
        "clarify_answer": clarify_answer,
        "trace": [],
    }

    config = {
        "configurable": {
            "runner": runner,
            "cache_store": cache_store,
            "resources": resources,
            "max_rows": max_rows,
            "timeout_ms": timeout_ms,
        }
    }

    final_state = graph.invoke(initial_state, config=config)

    action = final_state.get("action", "answer")

    # 组装 ChainResult
    result: dict | None = None
    clarify: dict | None = None
    reject: dict | None = None

    if action == "answer":
        result = final_state.get("result") or {
            "columns": final_state.get("columns", []),
            "rows": final_state.get("rows", []),
            "chart": final_state.get("chart_spec"),
            "narrative": final_state.get("narrative", ""),
            "truncated": final_state.get("truncated", False),
        }
        # 后端落库需要 query_spec / sql / chart_spec（溯源与存报表用）
        result["query_spec"] = final_state.get("query_spec")
        result["sql"] = final_state.get("sql")
        result["chart_spec"] = final_state.get("chart_spec")
    elif action == "clarify":
        clarify = final_state.get("clarify")
    elif action == "reject":
        reject = final_state.get("reject")

    # 缓存写回：仅 answer 且 rows 非空
    rows = (result or {}).get("rows", []) if action == "answer" else []
    if action == "answer" and rows:
        try:
            cache_store.put(
                final_state.get("cache_key", question),
                {
                    "query_spec": final_state.get("query_spec"),
                    "sql": final_state.get("sql"),
                    "chart_spec": final_state.get("chart_spec"),
                },
            )
        except Exception:
            pass  # 缓存写失败不影响主流程

    return ChainResult(
        action=action,
        result=result,
        clarify=clarify,
        reject=reject,
        trace=final_state.get("trace", []),
    )
