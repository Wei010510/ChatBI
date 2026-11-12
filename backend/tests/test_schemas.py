"""schemas 互斥校验测试（AC-4）。"""
import pytest

from app.core.exceptions import InternalError
from app.schemas import ChainResultOut


class TestChainResultMutualExclusion:
    def test_answer_result_nonempty_ok(self):
        cr = ChainResultOut(
            action="answer",
            result={"columns": [], "rows": []},
            clarify=None,
            reject=None,
        )
        assert cr.action == "answer"

    def test_clarify_with_result_raises_500(self):
        with pytest.raises(InternalError):
            ChainResultOut(
                action="clarify",
                result={"columns": []},
                clarify={"clarify_id": "c1"},
                reject=None,
            )

    def test_reject_with_result_raises_500(self):
        with pytest.raises(InternalError):
            ChainResultOut(
                action="reject",
                result={"columns": []},
                clarify=None,
                reject={"reason_code": "timeout"},
            )

    def test_clarify_no_result_ok(self):
        cr = ChainResultOut(
            action="clarify",
            result=None,
            clarify={"clarify_id": "c1"},
            reject=None,
        )
        assert cr.action == "clarify"

    def test_reject_no_result_ok(self):
        cr = ChainResultOut(
            action="reject",
            result=None,
            clarify=None,
            reject={"reason_code": "timeout"},
        )
        assert cr.action == "reject"
