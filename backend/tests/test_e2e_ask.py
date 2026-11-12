"""端到端问数测试（AC-4 / AC-7 / AC-16 / AC-17）。

Mock 算法 + Mock 仓储，验证 ask 流程落库与缓存写回条件。
"""
from unittest.mock import MagicMock, patch

from app.services import chat_service


def _mock_chain_result(action="answer", rows=None):
    rows = rows or [{"period": "2025", "gmv": 1000}]
    result = {
        "columns": [{"key": "period", "title": "周期", "type": "string"},
                    {"key": "gmv", "title": "GMV", "type": "number"}],
        "rows": rows,
        "chart": {"type": "bar", "x_field": "period", "series": [{"key": "gmv", "name": "GMV"}]},
        "narrative": "GMV 1000",
        "truncated": False,
        "query_spec": {"metrics": ["GMV"]},
        "sql": "SELECT channel, SUM(pay_amount) FROM dwd_order GROUP BY channel",
        "chart_spec": {"type": "bar"},
    }
    return {
        "action": action,
        "result": result if action == "answer" else None,
        "clarify": None if action != "clarify" else {"clarify_id": "c1", "missing": ["channel"]},
        "reject": None,
        "trace": [{"node": "understand", "elapsed_ms": 10}],
    }


def test_ask_creates_session_and_messages():
    db = MagicMock()
    with patch("app.services.chat_service.agent_ask", return_value=_mock_chain_result("answer")), \
         patch("app.services.chat_service.repo") as mock_repo:
        mock_repo.get_session.return_value = None
        mock_repo.create_session.return_value = MagicMock(id="s_1")
        mock_repo.get_recent_history.return_value = []
        mock_repo.create_message.side_effect = [
            MagicMock(id="m_user"), MagicMock(id="m_asst", clarify_state=None)
        ]

        result = chat_service.ask(db, question="GMV 多少", session_id=None)

        assert result["action"] == "answer"
        assert result["session_id"] == "s_1"
        # user + assistant 两条消息
        assert mock_repo.create_message.call_count == 2
        # trace 写 query_logs
        mock_repo.create_query_log.assert_called_once()


def test_ask_clarify_does_not_cache():
    """clarify 出口不写缓存。"""
    db = MagicMock()
    with patch("app.services.chat_service.agent_ask", return_value=_mock_chain_result("clarify")), \
         patch("app.services.chat_service.repo") as mock_repo:
        mock_repo.get_session.return_value = None
        mock_repo.create_session.return_value = MagicMock(id="s_1")
        mock_repo.get_recent_history.return_value = []
        mock_repo.create_message.side_effect = [
            MagicMock(id="m_user"), MagicMock(id="m_asst", clarify_state={"clarify_id": "c1"})
        ]

        result = chat_service.ask(db, question="什么渠道好", session_id=None)

        assert result["action"] == "clarify"
        # clarify_state 已落库
        call_kwargs = mock_repo.create_message.call_args_list[1].kwargs
        assert call_kwargs["clarify_state"] is not None
