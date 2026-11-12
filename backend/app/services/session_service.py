"""会话服务（SDD FR-7）。"""
from sqlalchemy.orm import Session as DbSession

from ..storage import repository as repo


def list_sessions(db: DbSession, limit: int = 30) -> list:
    sessions = repo.list_sessions(db, limit=limit)
    return [
        {
            "id": s.id,
            "title": s.title,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sessions
    ]


def get_messages(db: DbSession, session_id: str) -> list:
    from ..core.exceptions import SessionNotFound

    if not repo.get_session(db, session_id):
        raise SessionNotFound()
    msgs = repo.get_messages(db, session_id)
    items = []
    for m in msgs:
        item = {
            "message_id": m.id,
            "session_id": m.session_id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        if m.role == "assistant":
            item["action"] = m.action
            if m.payload:
                p = dict(m.payload)
                p.pop("trace", None)
                item["result"] = p.get("result")
                item["clarify"] = p.get("clarify")
                item["reject"] = p.get("reject")
        items.append(item)
    return items


def delete_session(db: DbSession, session_id: str) -> None:
    from ..core.exceptions import SessionNotFound

    session = repo.get_session(db, session_id)
    if not session:
        raise SessionNotFound()
    repo.delete_session(db, session)


def delete_all_sessions(db: DbSession) -> int:
    return repo.delete_all_sessions(db)
