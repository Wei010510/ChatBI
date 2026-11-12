"""ResourceProvider 实现（SDD §3 / FR-14）。

l0() 调 introspection；l1() 读 metrics.yaml；templates/exemplars/aliases 读 YAML。
任一缺失不报错（零资源可用 NFR-5）。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from ..core.config import get_settings
from ..query.introspection import PgIntrospector
from . import retrieval

logger = logging.getLogger(__name__)
settings = get_settings()

_SEMANTICS_DIR = Path(__file__).resolve().parents[2] / "semantics"


class ResourceProvider:
    """算法 ResourceProvider 协议的实现。"""

    def __init__(self, introspector: PgIntrospector | None = None):
        self._introspector = introspector or PgIntrospector()
        self._pgvector_available = retrieval.detect_pgvector()
        logger.info("pgvector available: %s", self._pgvector_available)

    # ---------- L0 硬依赖 ----------
    def l0(self) -> dict:
        return self._introspector.l0()

    # ---------- L1 口径词典（增强包，可选） ----------
    def l1(self) -> dict:
        return self._load_yaml(_SEMANTICS_DIR / "metrics.yaml", default={})

    # ---------- 模板（可选） ----------
    def templates(self) -> list[dict]:
        return self._load_yaml_section(_SEMANTICS_DIR / "templates.yaml", "templates")

    def template_version(self) -> str:
        data = self._load_yaml(_SEMANTICS_DIR / "templates.yaml", default={})
        return str(data.get("version") or "") if isinstance(data, dict) else ""

    # ---------- 示例检索（有向量走向量，无向量降级关键词） ----------
    _EXEMPLAR_TOP_K = 5

    def exemplars(self, question: str = "") -> list[dict]:
        items = self._load_yaml_section(_SEMANTICS_DIR / "exemplars.yaml", "exemplars")
        if not question or not items:
            return items
        if self._pgvector_available:
            hits = retrieval.vector_search(question, top_k=self._EXEMPLAR_TOP_K)
            by_id = {str(ex.get("id")): ex for ex in items}
            recalled = [by_id[str(h["exemplar_id"])] for h in hits
                        if str(h.get("exemplar_id")) in by_id]
            if recalled:
                return recalled
        return retrieval.lexical_search(question, items, top_k=self._EXEMPLAR_TOP_K)

    def exemplar_version(self) -> str:
        data = self._load_yaml(_SEMANTICS_DIR / "exemplars.yaml", default={})
        return str(data.get("version") or "") if isinstance(data, dict) else ""

    # ---------- 实体别名（可选） ----------
    def aliases(self) -> dict:
        return self._load_yaml(_SEMANTICS_DIR / "aliases.yaml", default={})

    # ---------- 工具方法 ----------
    @staticmethod
    def _load_yaml(path: Path, *, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            with path.open("r", encoding="utf-8") as f:
                return yaml.safe_load(f) or default
        except Exception as e:
            logger.warning("加载 %s 失败: %s", path.name, e)
            return default

    @classmethod
    def _load_yaml_section(cls, path: Path, key: str) -> list[dict]:
        data = cls._load_yaml(path, default={})
        if not isinstance(data, dict):
            return []
        section = data.get(key)
        if not isinstance(section, list):
            return []
        return [item for item in section if isinstance(item, dict)]
