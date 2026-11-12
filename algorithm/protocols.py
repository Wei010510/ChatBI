"""与后端的运行期协议：QueryRunner / CacheStore / ResourceProvider（SDD §9.2 / §9.4）。

算法只定义 Protocol，不做实现；本文件附 Mock 实现供单测使用。
"""
from typing import Any, Literal, Protocol, TypedDict


class QueryResult(TypedDict):
    columns: list[dict]
    rows: list[dict]
    row_count: int
    truncated: bool
    elapsed_ms: int
    error_code: Literal["SQL_REJECTED", "SQL_FAILED", "QUERY_TIMEOUT"] | None
    message: str | None


class QueryRunner(Protocol):
    def run(
        self,
        sql: str,
        *,
        params: dict | None = None,
        timeout_ms: int | None = None,
        max_rows: int | None = None,
    ) -> QueryResult: ...


class CacheStore(Protocol):
    def get(self, key: str) -> dict | None: ...
    def put(self, key: str, value: dict) -> None: ...


class ResourceProvider(Protocol):
    def l0(self) -> dict: ...
    def l1(self) -> dict: ...
    def templates(self) -> list[dict]: ...
    def template_version(self) -> str: ...
    def exemplars(self, question: str = "") -> list[dict]: ...
    def aliases(self) -> dict: ...


# ---------- Mock 实现（供算法侧单测） ----------

class MockQueryRunner:
    """可配置 error_code / rows 的 QueryRunner Mock。"""

    def __init__(
        self,
        *,
        rows: list[dict] | None = None,
        columns: list[dict] | None = None,
        error_code: str | None = None,
        message: str | None = None,
        truncated: bool = False,
        call_sequence: list[dict] | None = None,
    ):
        self._rows = rows or []
        self._columns = columns or []
        self._error_code = error_code
        self._message = message
        self._truncated = truncated
        # 调用序列：每次 run 按序取一个配置，用于模拟首次失败二次成功等场景
        self._sequence = call_sequence or []
        self._seq_idx = 0
        self.calls: list[dict] = []

    def run(self, sql, *, params=None, timeout_ms=None, max_rows=None):
        self.calls.append({"sql": sql, "params": params})
        if self._sequence and self._seq_idx < len(self._sequence):
            cfg = self._sequence[self._seq_idx]
            self._seq_idx += 1
            return self._build(cfg)
        return self._build({
            "rows": self._rows, "columns": self._columns,
            "error_code": self._error_code, "message": self._message,
            "truncated": self._truncated,
        })

    def _build(self, cfg):
        rows = cfg.get("rows", [])
        columns = cfg.get("columns", [])
        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            truncated=cfg.get("truncated", False),
            elapsed_ms=10,
            error_code=cfg.get("error_code"),
            message=cfg.get("message"),
        )


class MemoryCacheStore:
    """内存 CacheStore Mock，记录 put 调用。"""

    def __init__(self):
        self._store: dict[str, dict] = {}
        self.put_calls: list[tuple[str, dict]] = []

    def get(self, key):
        return self._store.get(key)

    def put(self, key, value):
        self._store[key] = value
        self.put_calls.append((key, dict(value)))


class MockResourceProvider:
    """可独立开关各类资源的 ResourceProvider Mock。"""

    def __init__(
        self,
        *,
        l0: dict | None = None,
        l1: dict | None = None,
        templates: list[dict] | None = None,
        template_version: str = "",
        exemplars: list[dict] | None = None,
        aliases: dict | None = None,
    ):
        self._l0 = l0 or {"tables": [], "columns": [], "data_range": {}, "schema_version": "v0"}
        self._l1 = l1 or {}
        self._templates = templates or []
        self._template_version = template_version
        self._exemplars = exemplars or []
        self._aliases = aliases or {}

    def l0(self):
        return self._l0

    def l1(self):
        return self._l1

    def templates(self):
        return self._templates

    def template_version(self):
        return self._template_version

    def exemplars(self, question: str = ""):
        return self._exemplars

    def aliases(self):
        return self._aliases
