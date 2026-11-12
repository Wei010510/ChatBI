"""依赖注入：get_current_user 恒返回 demo；get_db（SDD FR-3 / §7）。"""
from collections.abc import Generator
from typing import TypedDict

from fastapi import Depends
from sqlalchemy.orm import Session

from .config import get_settings
from ..storage.session import SessionLocal


class CurrentUser(TypedDict):
    user_id: str


def get_current_user() -> CurrentUser:
    """鉴权预留：本版恒返回 demo。"""
    return {"user_id": "demo"}


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
