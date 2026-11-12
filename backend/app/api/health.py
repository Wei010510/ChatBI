"""健康检查（SDD FR-9）。"""
from fastapi import APIRouter

from .responses import ok

router = APIRouter()


@router.get("/health")
def health():
    return ok({"status": "ok"})
