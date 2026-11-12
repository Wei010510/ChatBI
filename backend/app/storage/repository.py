"""仓储层：各表 CRUD，查询默认带 user_id='demo'（SDD §7）。"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, desc, orm

from ..core.config import get_settings
from ..core.ids import gen_id
from .models import Message, QueryLog, Report, SemanticCache, Session

settings = get_settings()

USER_ID = "demo"


# ---------- Sessions ----------

def create_session(db: orm.Session, *, title: str = "新对话") -> Session:
    session = Session(id=gen_id("s"), title=title or "新对话", user_id=USER_ID)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: orm.Session, session_id: str) -> Session | None:
    return (
        db.query(Session)
        .filter(and_(Session.id == session_id, Session.user_id == USER_ID))
        .first()
    )


def list_sessions(db: orm.Session, limit: int = 30) -> list[Session]:
    return (
        db.query(Session)
        .filter(Session.user_id == USER_ID)
        .order_by(desc(Session.updated_at))
        .limit(limit)
        .all()
    )


def touch_session(db: orm.Session, session: Session) -> None:
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()


def delete_session(db: orm.Session, session: Session) -> None:
    """删除会话，消息按 relationship 的 delete-orphan 级联删除。"""
    db.delete(session)
    db.commit()


def delete_all_sessions(db: orm.Session) -> int:
    """清空当前用户全部会话，返回删除条数。"""
    sessions = db.query(Session).filter(Session.user_id == USER_ID).all()
    for s in sessions:
        db.delete(s)
    db.commit()
    return len(sessions)


# ---------- Messages ----------

def create_message(
    db: orm.Session,
    *,
    session_id: str,
    role: str,
    content: str | None = None,
    action: str | None = None,
    payload: dict | None = None,
    query_spec: dict | None = None,
    sql: str | None = None,
    chart_spec: dict | None = None,
    clarify_state: dict | None = None,
) -> Message:
    msg = Message(
        id=gen_id("m"),
        session_id=session_id,
        user_id=USER_ID,
        role=role,
        content=content,
        action=action,
        payload=payload,
        query_spec=query_spec,
        sql=sql,
        chart_spec=chart_spec,
        clarify_state=clarify_state,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_message(db: orm.Session, message_id: str) -> Message | None:
    return db.query(Message).filter(Message.id == message_id).first()


def get_messages(db: orm.Session, session_id: str, limit: int = 100) -> list[Message]:
    return (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at)
        .limit(limit)
        .all()
    )


def get_recent_history(db: orm.Session, session_id: str, rounds: int = 6) -> list[dict]:
    """读最近 N 轮（user+assistant 配对），返回给算法的 history。

    形状按 SDD-算法应用 §9.1：[{role, content, query_spec}]，只带槽位摘要，不含 rows。
    """
    msgs = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(desc(Message.created_at))
        .limit(rounds * 2)
        .all()
    )
    msgs = list(reversed(msgs))
    history = []
    for m in msgs:
        if m.role == "user":
            history.append({"role": "user", "content": m.content or ""})
        elif m.role == "assistant":
            entry = {"role": "assistant", "action": m.action}
            if m.query_spec:
                entry["query_spec"] = m.query_spec
            history.append(entry)
    return history


def clear_clarify_state(db: orm.Session, message_id: str) -> None:
    msg = get_message(db, message_id)
    if msg and msg.clarify_state:
        msg.clarify_state = None
        db.add(msg)
        db.commit()


# ---------- Reports ----------

def create_report(
    db: orm.Session,
    *,
    name: str,
    source_message_id: str,
    question: str | None,
    query_spec: dict | None,
    sql: str | None,
    chart_spec: dict | None,
    narrative: str | None,
    snapshot_columns: list[dict],
    snapshot_rows: list[dict],
    snapshot_truncated: bool,
) -> Report:
    report = Report(
        id=gen_id("r"),
        user_id=USER_ID,
        name=name,
        source_message_id=source_message_id,
        question=question,
        query_spec=query_spec,
        sql=sql,
        chart_spec=chart_spec,
        narrative=narrative,
        snapshot_columns=snapshot_columns,
        snapshot_rows=snapshot_rows,
        snapshot_truncated=snapshot_truncated,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_report(db: orm.Session, report_id: str) -> Report | None:
    return (
        db.query(Report)
        .filter(and_(Report.id == report_id, Report.user_id == USER_ID))
        .first()
    )


def get_report_by_name(db: orm.Session, name: str) -> Report | None:
    return (
        db.query(Report)
        .filter(and_(Report.name == name, Report.user_id == USER_ID))
        .first()
    )


def list_reports(db: orm.Session, page: int = 1, size: int = 20) -> tuple[list[Report], int]:
    q = db.query(Report).filter(Report.user_id == USER_ID)
    total = q.count()
    items = (
        q.order_by(desc(Report.updated_at))
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return items, total


def rename_report(db: orm.Session, report: Report, name: str) -> Report:
    report.name = name
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def delete_report(db: orm.Session, report: Report) -> None:
    db.delete(report)
    db.commit()


# ---------- Semantic Cache ----------

def get_cache(db: orm.Session, cache_key: str) -> SemanticCache | None:
    item = (
        db.query(SemanticCache)
        .filter(SemanticCache.cache_key == cache_key)
        .first()
    )
    if item and item.expires_at and item.expires_at < datetime.now(timezone.utc):
        return None
    return item


def put_cache(
    db: orm.Session,
    *,
    cache_key: str,
    query_spec: dict | None,
    sql: str | None,
    chart_spec: dict | None,
    l1_version: str = "",
    schema_version: str = "",
    template_version: str = "",
    source: str = "generated",
) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.cache_ttl_seconds)
    item = get_cache(db, cache_key)
    if item:
        item.query_spec = query_spec
        item.sql = sql
        item.chart_spec = chart_spec
        item.l1_version = l1_version
        item.schema_version = schema_version
        item.template_version = template_version
        item.source = source
        item.hit_count = (item.hit_count or 0) + 1
        item.expires_at = expires_at
    else:
        item = SemanticCache(
            cache_key=cache_key,
            query_spec=query_spec,
            sql=sql,
            chart_spec=chart_spec,
            l1_version=l1_version,
            schema_version=schema_version,
            template_version=template_version,
            source=source,
            hit_count=1,
            expires_at=expires_at,
        )
        db.add(item)
    db.commit()


# ---------- Query Logs ----------

def create_query_log(
    db: orm.Session,
    *,
    message_id: str,
    sql: str | None = None,
    row_count: int = 0,
    elapsed_ms: int = 0,
    error_code: str | None = None,
    cached: bool = False,
    trace: list[dict] | None = None,
) -> QueryLog:
    log = QueryLog(
        message_id=message_id,
        sql=sql,
        row_count=row_count,
        elapsed_ms=elapsed_ms,
        error_code=error_code,
        cached=cached,
        trace=trace or [],
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
