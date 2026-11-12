"""报表约束测试（AC-12 / AC-13）。"""
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import MessageNotQueryable, ReportNameExists
from app.services import report_service


def _answer_message(rows=None):
    if rows is None:
        rows = [{"a": 1}]
    payload = {
        "result": {
            "columns": [{"key": "a"}],
            "rows": rows,
            "chart": {"type": "bar"},
            "narrative": "test",
            "truncated": False,
        }
    }
    msg = MagicMock()
    msg.id = "m_1"
    msg.action = "answer"
    msg.content = "GMV 多少"
    msg.query_spec = {"metrics": ["GMV"]}
    msg.sql = "SELECT ..."
    msg.chart_spec = {"type": "bar", "x_field": "x", "series": [{"key": "gmv"}]}
    msg.payload = payload
    return msg


def test_create_report_from_answer_ok():
    db = MagicMock()
    with patch("app.services.report_service.repo") as mock_repo:
        mock_repo.get_message.return_value = _answer_message()
        mock_repo.get_report_by_name.return_value = None
        mock_repo.create_report.return_value = MagicMock(id="r_1", name="报表1")

        result = report_service.create_report(db, message_id="m_1", name="报表1")
        assert result["id"] == "r_1"


def test_create_report_non_answer_rejected():
    db = MagicMock()
    msg = MagicMock(id="m_1", action="clarify")
    with patch("app.services.report_service.repo") as mock_repo:
        mock_repo.get_message.return_value = msg
        with pytest.raises(MessageNotQueryable):
            report_service.create_report(db, message_id="m_1", name="报表1")


def test_create_report_empty_rows_rejected():
    db = MagicMock()
    with patch("app.services.report_service.repo") as mock_repo:
        mock_repo.get_message.return_value = _answer_message(rows=[])
        mock_repo.get_report_by_name.return_value = None
        with pytest.raises(MessageNotQueryable):
            report_service.create_report(db, message_id="m_1", name="报表1")


def test_create_report_duplicate_name_conflict():
    db = MagicMock()
    with patch("app.services.report_service.repo") as mock_repo:
        mock_repo.get_message.return_value = _answer_message()
        mock_repo.get_report_by_name.return_value = MagicMock(id="r_old")
        with pytest.raises(ReportNameExists):
            report_service.create_report(db, message_id="m_1", name="报表1", overwrite=False)


def test_get_report_uses_snapshot_no_runner():
    """GET 报表只读快照，不调用 runner（NFR-3）。"""
    db = MagicMock()
    report = MagicMock(
        id="r_1", name="报表1", question="GMV",
        snapshot_columns=[{"key": "a"}],
        snapshot_rows=[{"a": 1}],
        snapshot_truncated=False,
        chart_spec={"type": "bar"},
        narrative="test",
        created_at=None,
    )
    with patch("app.services.report_service.repo") as mock_repo:
        mock_repo.get_report.return_value = report
        result = report_service.get_report(db, "r_1")
        assert result["result"]["rows"] == [{"a": 1}]
        # 不调用 runner（repo 中没有 runner 调用）
        assert not any("runner" in str(c) for c in mock_repo.method_calls)
