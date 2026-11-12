"""会话接口：GET /sessions、GET /sessions/{id}/messages（SDD FR-7）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.deps import get_db
from ..services import session_service
from .responses import ok

router = APIRouter(prefix="/sessions")


@router.get("")
def list_sessions(limit: int = Query(30, ge=1, le=100), db: Session = Depends(get_db)):
    items = session_service.list_sessions(db, limit=limit)
    return ok({"items": items})


@router.get("/{session_id}/messages")
def get_messages(session_id: str, db: Session = Depends(get_db)):
    items = session_service.get_messages(db, session_id)
    return ok({"items": items})


@router.delete("/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    session_service.delete_session(db, session_id)
    return ok({"deleted": True})


@router.delete("")
def delete_all_sessions(db: Session = Depends(get_db)):
    deleted_count = session_service.delete_all_sessions(db)
    return ok({"deleted_count": deleted_count})
