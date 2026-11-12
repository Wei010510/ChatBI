"""报表服务（SDD FR-8）。

存为报表：message 必须是 answer 且 rows 非空（否则 422）。
打开报表：只读快照，不执行 SQL、不调算法（NFR-3）。
"""
from sqlalchemy.orm import Session as DbSession

from ..core.exceptions import (
    MessageNotQueryable,
    ReportNameExists,
    ReportNotFound,
)
from ..storage import repository as repo

ALLOWED_CHART_TYPES = {"bar", "line"}


def create_report(
    db: DbSession,
    *,
    message_id: str,
    name: str,
    chart_type: str | None = None,
    overwrite: bool = False,
) -> dict:
    msg = repo.get_message(db, message_id)
    if not msg:
        raise MessageNotQueryable("消息不存在")

    # 校验：必须是 answer 且 rows 非空
    if msg.action != "answer":
        raise MessageNotQueryable("该消息不是 answer 类型")

    result = (msg.payload or {}).get("result") or {}
    rows = result.get("rows", [])
    if not rows:
        raise MessageNotQueryable("该消息结果为空，不可存为报表")

    # chart_type 只能 bar/line
    if chart_type and chart_type not in ALLOWED_CHART_TYPES:
        raise MessageNotQueryable(f"chart_type 只能是 {ALLOWED_CHART_TYPES}")

    # 同名处理
    existing = repo.get_report_by_name(db, name)
    if existing and not overwrite:
        raise ReportNameExists()
    if existing and overwrite:
        repo.delete_report(db, existing)

    # chart_spec：用消息的，chart_type 只覆盖 type
    chart_spec = msg.chart_spec or result.get("chart") or {}
    if chart_type and chart_spec:
        chart_spec = {**chart_spec, "type": chart_type}

    report = repo.create_report(
        db,
        name=name,
        source_message_id=message_id,
        question=msg.content,
        query_spec=msg.query_spec,
        sql=msg.sql,
        chart_spec=chart_spec,
        narrative=result.get("narrative"),
        snapshot_columns=result.get("columns", []),
        snapshot_rows=rows,
        snapshot_truncated=result.get("truncated", False),
    )

    return {"id": report.id, "name": report.name}


def list_reports(db: DbSession, page: int = 1, size: int = 20) -> dict:
    items, total = repo.list_reports(db, page=page, size=size)
    return {
        "items": [
            {
                "id": r.id,
                "name": r.name,
                "question": r.question,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in items
        ],
        "total": total,
    }


def get_report(db: DbSession, report_id: str) -> dict:
    """只读快照：直接读 snapshot_* 组装 result，不执行 SQL、不调算法。"""
    report = repo.get_report(db, report_id)
    if not report:
        raise ReportNotFound()

    result = {
        "columns": report.snapshot_columns or [],
        "rows": report.snapshot_rows or [],
        "chart": report.chart_spec,
        "narrative": report.narrative,
        "truncated": report.snapshot_truncated or False,
    }

    return {
        "id": report.id,
        "name": report.name,
        "question": report.question,
        "result": result,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def rename_report(db: DbSession, report_id: str, name: str) -> dict:
    report = repo.get_report(db, report_id)
    if not report:
        raise ReportNotFound()
    report = repo.rename_report(db, report, name)
    return {"id": report.id, "name": report.name}


def delete_report(db: DbSession, report_id: str) -> dict:
    report = repo.get_report(db, report_id)
    if not report:
        raise ReportNotFound()
    repo.delete_report(db, report)
    return {"deleted": True}
