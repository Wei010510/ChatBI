"""报表接口：POST/GET/PATCH/DELETE /reports（SDD FR-8）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.deps import get_db
from ..schemas import ReportCreateRequest, ReportUpdateRequest
from ..services import report_service
from .responses import ok

router = APIRouter(prefix="/reports")


@router.post("")
def create_report(req: ReportCreateRequest, db: Session = Depends(get_db)):
    result = report_service.create_report(
        db,
        message_id=req.message_id,
        name=req.name,
        chart_type=req.chart_type,
        overwrite=req.overwrite,
    )
    return ok(result)


@router.get("")
def list_reports(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    result = report_service.list_reports(db, page=page, size=size)
    return ok(result)


@router.get("/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    result = report_service.get_report(db, report_id)
    return ok(result)


@router.patch("/{report_id}")
def update_report(report_id: str, req: ReportUpdateRequest, db: Session = Depends(get_db)):
    result = report_service.rename_report(db, report_id, req.name)
    return ok(result)


@router.delete("/{report_id}")
def delete_report(report_id: str, db: Session = Depends(get_db)):
    result = report_service.delete_report(db, report_id)
    return ok(result)
