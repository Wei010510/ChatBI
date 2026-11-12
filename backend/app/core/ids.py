"""ID 生成：s_/m_/r_ 前缀 + ULID。"""
import ulid


def gen_id(prefix: str) -> str:
    return f"{prefix}_{ulid.new().str}"
