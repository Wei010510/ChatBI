"""问数服务：ask + clarify（SDD FR-5 / FR-6）。

services 是唯一调算法的层（AC-1）。
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session as DbSession

from algorithm import ask as agent_ask

from ..core.config import get_settings
from ..core.exceptions import ClarifyExpired, SessionNotFound
from ..query.cache_store import PgCacheStore
from ..query.runner import PgQueryRunner
from ..resources.provider import ResourceProvider
from ..storage import repository as repo

settings = get_settings()

CLARIFY_TTL_SECONDS = 600  # 澄清 10 分钟过期


def _build_dependencies():
    runner = PgQueryRunner()
    cache_store = PgCacheStore()
    resources = ResourceProvider()
    return runner, cache_store, resources


def ask(db: DbSession, *, question: str, session_id: str | None) -> dict:
    """一次问数：新建/取会话 → 读历史 → 调算法 → 落库 → 返回。"""
    # 1. 会话
    if session_id:
        session = repo.get_session(db, session_id)
        if not session:
            raise SessionNotFound()
    else:
        title = question[:24] if question else "新对话"
        session = repo.create_session(db, title=title)
        session_id = session.id

    # 2. 历史（最近 6 轮）
    history = repo.get_recent_history(db, session_id, rounds=6)

    # 3. 调算法
    runner, cache_store, resources = _build_dependencies()
    chain_result = agent_ask(
        question,
        session_id=session_id,
        history=history,
        runner=runner,
        cache_store=cache_store,
        resources=resources,
        max_rows=settings.max_rows,
        timeout_ms=settings.query_timeout_ms,
    )

    # 4. 落 user 消息
    repo.create_message(
        db,
        session_id=session_id,
        role="user",
        content=question,
    )

    # 5. 落 assistant 消息（payload 不含 trace）
    action = chain_result["action"]
    payload = {
        "action": action,
        "result": chain_result.get("result"),
        "clarify": chain_result.get("clarify"),
        "reject": chain_result.get("reject"),
    }

    query_spec = None
    sql = None
    chart_spec = None
    clarify_state = None
    content = None

    if action == "answer":
        result = chain_result.get("result") or {}
        query_spec = result.get("query_spec")
        sql = result.get("sql")
        chart_spec = result.get("chart_spec") or result.get("chart")
        content = result.get("narrative")
    elif action == "clarify":
        clarify = chain_result.get("clarify") or {}
        clarify_id = clarify.get("clarify_id") or f"c_{session_id}"
        clarify_state = {
            "clarify_id": clarify_id,
            "original_question": question,
            "missing": clarify.get("missing", []),
            "options": clarify.get("options", []),
            "expires_at": (datetime.utcnow() + timedelta(seconds=CLARIFY_TTL_SECONDS)).isoformat(),
        }

    assistant_msg = repo.create_message(
        db,
        session_id=session_id,
        role="assistant",
        content=content,
        action=action,
        payload=payload,
        query_spec=query_spec,
        sql=sql,
        chart_spec=chart_spec,
        clarify_state=clarify_state,
    )

    # 6. trace 写 query_logs
    trace = chain_result.get("trace", [])
    repo.create_query_log(
        db,
        message_id=assistant_msg.id,
        sql=sql,
        row_count=len((chain_result.get("result") or {}).get("rows", [])) if action == "answer" else 0,
        error_code=None,
        cached=False,
        trace=trace,
    )

    # 7. 触达会话
    repo.touch_session(db, session)

    # 8. 返回 ChatAnswer
    return {
        "message_id": assistant_msg.id,
        "session_id": session_id,
        "action": action,
        "result": chain_result.get("result"),
        "clarify": chain_result.get("clarify"),
        "reject": chain_result.get("reject"),
    }


def clarify(db: DbSession, *, session_id: str, clarify_id: str, answer: dict) -> dict:
    """提交澄清：结构化补全调算法，不拼自然语言（SDD FR-6）。"""
    session = repo.get_session(db, session_id)
    if not session:
        raise SessionNotFound()

    # 找到含该 clarify_id 的消息
    msgs = repo.get_messages(db, session_id)
    clarify_msg = None
    for m in reversed(msgs):
        if m.clarify_state and m.clarify_state.get("clarify_id") == clarify_id:
            clarify_msg = m
            break

    if not clarify_msg:
        raise ClarifyExpired()

    state = clarify_msg.clarify_state
    expires_at = state.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) < datetime.utcnow():
        raise ClarifyExpired()

    original_question = state.get("original_question", "")

    # 用户的澄清答案落为 user 消息（选项取 label，自由文本取原文），保证多槽位澄清逐轮收敛、回放可见（SDD §2.2）
    answer_content = str(answer.get("text") or "").strip()
    if not answer_content:
        value = str(answer.get("value") or "").strip()
        answer_content = next(
            (str(o.get("label")) for o in state.get("options", []) if str(o.get("value")) == value),
            value,
        )
    if answer_content:
        repo.create_message(db, session_id=session_id, role="user", content=answer_content)

    # 结构化补全：直接把 clarify_answer 传给算法 S1，不拼自然语言；history 与 /api/chat/ask 一致携带最近 6 轮（SDD §2.2）
    history = repo.get_recent_history(db, session_id, rounds=6)
    runner, cache_store, resources = _build_dependencies()
    chain_result = agent_ask(
        original_question,
        session_id=session_id,
        history=history,
        clarify_answer=answer,
        runner=runner,
        cache_store=cache_store,
        resources=resources,
        max_rows=settings.max_rows,
        timeout_ms=settings.query_timeout_ms,
    )

    # 清空原 clarify_state
    repo.clear_clarify_state(db, clarify_msg.id)

    # 落 assistant 消息
    action = chain_result["action"]
    payload = {
        "action": action,
        "result": chain_result.get("result"),
        "clarify": chain_result.get("clarify"),
        "reject": chain_result.get("reject"),
    }

    query_spec = None
    sql = None
    chart_spec = None
    content = None
    clarify_state = None
    if action == "answer":
        result = chain_result.get("result") or {}
        query_spec = result.get("query_spec")
        sql = result.get("sql")
        chart_spec = result.get("chart_spec") or result.get("chart")
        content = result.get("narrative")
    elif action == "clarify":
        # 链式澄清：新澄清同样要暂存 clarify_state，否则下一轮提交永远 CLARIFY_EXPIRED
        clarify = chain_result.get("clarify") or {}
        new_clarify_id = clarify.get("clarify_id") or f"c_{session_id}"
        clarify_state = {
            "clarify_id": new_clarify_id,
            "original_question": original_question,
            "missing": clarify.get("missing", []),
            "options": clarify.get("options", []),
            "expires_at": (datetime.utcnow() + timedelta(seconds=CLARIFY_TTL_SECONDS)).isoformat(),
        }

    assistant_msg = repo.create_message(
        db,
        session_id=session_id,
        role="assistant",
        content=content,
        action=action,
        payload=payload,
        query_spec=query_spec,
        sql=sql,
        chart_spec=chart_spec,
        clarify_state=clarify_state,
    )

    repo.create_query_log(
        db,
        message_id=assistant_msg.id,
        sql=sql,
        row_count=len((chain_result.get("result") or {}).get("rows", [])) if action == "answer" else 0,
        trace=chain_result.get("trace", []),
    )

    repo.touch_session(db, session)

    return {
        "message_id": assistant_msg.id,
        "session_id": session_id,
        "action": action,
        "result": chain_result.get("result"),
        "clarify": chain_result.get("clarify"),
        "reject": chain_result.get("reject"),
    }
