"""Pydantic 入参/出参模型（SDD §2）。"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, model_validator

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应包：{code, message, data, trace_id}。"""

    code: str = "0"
    message: str = "ok"
    data: T | None = None
    trace_id: str = ""


# ---------- ChainResult 透传（SDD §7.4） ----------

class ChainResultOut(BaseModel):
    """算法 ChainResult（不含 trace，trace 剥离到 query_logs）。"""

    action: str
    result: dict | None = None
    clarify: dict | None = None
    reject: dict | None = None

    @model_validator(mode="after")
    def check_mutual_exclusion(self) -> "ChainResultOut":
        """result/clarify/reject 互斥：clarify/reject 状态下 result 非空 → 500。"""
        if self.action in ("clarify", "reject"):
            if self.result:
                from ..core.exceptions import InternalError

                raise InternalError(f"action={self.action} 时 result 必须为空")
        return self


class ChatAnswer(ChainResultOut):
    """一次问数返回：message_id + session_id + ChainResult。"""

    message_id: str
    session_id: str


# ---------- 入参 ----------

class ChatAskRequest(BaseModel):
    session_id: str | None = None
    question: str = Field(..., min_length=1)


class ChatClarifyRequest(BaseModel):
    session_id: str
    clarify_id: str
    answer: dict


class ReportCreateRequest(BaseModel):
    message_id: str
    name: str = Field(..., min_length=1)
    chart_type: str | None = None  # 只能 bar/line
    overwrite: bool = False


class ReportUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=1)


# ---------- 出参 ----------

class SessionItem(BaseModel):
    id: str
    title: str
    updated_at: str


class MessageItem(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str | None = None
    action: str | None = None
    result: dict | None = None
    clarify: dict | None = None
    reject: dict | None = None
    created_at: str


class ReportListItem(BaseModel):
    id: str
    name: str
    question: str | None = None
    created_at: str
    updated_at: str


class ReportDetail(BaseModel):
    id: str
    name: str
    question: str | None = None
    result: dict
    created_at: str
