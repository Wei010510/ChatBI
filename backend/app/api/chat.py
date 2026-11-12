"""问数接口：POST /chat/ask、POST /chat/clarify（SDD FR-5 / FR-6）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.deps import get_db
from ..schemas import ChatAnswer, ChatAskRequest, ChatClarifyRequest
from ..services import chat_service
from .responses import ok

router = APIRouter(prefix="/chat")


@router.post("/ask", response_model=dict)
def ask(req: ChatAskRequest, db: Session = Depends(get_db)):
    result = chat_service.ask(db, question=req.question, session_id=req.session_id)
    return ok(result)


@router.post("/clarify", response_model=dict)
def clarify(req: ChatClarifyRequest, db: Session = Depends(get_db)):
    result = chat_service.clarify(
        db,
        session_id=req.session_id,
        clarify_id=req.clarify_id,
        answer=req.answer,
    )
    return ok(result)
