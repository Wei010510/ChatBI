"""ORM 模型：5 张 app 表，字段与 SDD §4 完全一致。"""
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .session import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "app"}

    id = Column(String, primary_key=True)
    title = Column(Text, default="新对话")
    user_id = Column(String, default="demo", nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_session_id", "session_id"),
        {"schema": "app"},
    )

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("app.sessions.id"), nullable=False)
    user_id = Column(String, default="demo", nullable=False)
    role = Column(String, nullable=False)  # user / assistant
    content = Column(Text)  # 用户原始问题；助手消息存 narrative 或空
    action = Column(String)  # 仅 assistant：answer/clarify/reject；user 为 NULL
    payload = Column(JSONB)  # 仅 assistant：ChainResult（不含 trace）
    query_spec = Column(JSONB)  # 仅 answer
    sql = Column(Text)  # 仅 answer
    chart_spec = Column(JSONB)  # 仅 answer
    clarify_state = Column(JSONB)  # 仅 clarify
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    session = relationship("Session", back_populates="messages")


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_reports_user_name", "user_id", "name", unique=True),
        {"schema": "app"},
    )

    id = Column(String, primary_key=True)
    user_id = Column(String, default="demo", nullable=False)
    name = Column(Text, nullable=False)
    source_message_id = Column(String)
    question = Column(Text)
    query_spec = Column(JSONB)
    sql = Column(Text)
    chart_spec = Column(JSONB)
    narrative = Column(Text)
    snapshot_columns = Column(JSONB)
    snapshot_rows = Column(JSONB)
    snapshot_truncated = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class SemanticCache(Base):
    __tablename__ = "semantic_cache"
    __table_args__ = {"schema": "app"}

    cache_key = Column(String, primary_key=True)
    query_spec = Column(JSONB)
    sql = Column(Text)
    chart_spec = Column(JSONB)
    l1_version = Column(String, default="")
    schema_version = Column(String, default="")
    template_version = Column(String, default="")
    source = Column(String)  # template / generated
    hit_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class QueryLog(Base):
    __tablename__ = "query_logs"
    __table_args__ = {"schema": "app"}

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String)
    sql = Column(Text)
    row_count = Column(Integer, default=0)
    elapsed_ms = Column(Integer, default=0)
    error_code = Column(String)
    cached = Column(Boolean, default=False)
    trace = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
