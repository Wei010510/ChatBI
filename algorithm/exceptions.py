"""失败码枚举与 retryable 映射（与 SDD §5.3 一致）。"""
from enum import Enum


class RejectCode(str, Enum):
    # 业务不可答（retryable=false）
    OUT_OF_SCOPE = "out_of_scope"
    DETAIL_EXPORT = "detail_export"
    NO_DATA = "no_data"
    WRITE_OP = "write_op"

    # 技术失败（retryable=true）
    INTENT_PARSE_FAILED = "intent_parse_failed"
    SQL_GENERATE_FAILED = "sql_generate_failed"
    SQL_EXECUTE_FAILED = "sql_execute_failed"
    TIMEOUT = "timeout"


# 业务类 retryable=false，技术类 retryable=true
RETRYABLE_MAP = {
    RejectCode.OUT_OF_SCOPE: False,
    RejectCode.DETAIL_EXPORT: False,
    RejectCode.NO_DATA: False,
    RejectCode.WRITE_OP: False,
    RejectCode.INTENT_PARSE_FAILED: True,
    RejectCode.SQL_GENERATE_FAILED: True,
    RejectCode.SQL_EXECUTE_FAILED: True,
    RejectCode.TIMEOUT: True,
}


def is_retryable(code: RejectCode) -> bool:
    return RETRYABLE_MAP.get(code, False)
