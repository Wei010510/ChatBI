"""pgvector 探测、向量检索与 lexical 降级（SDD FR-14 / NFR-6）。

PGVECTOR_ENABLED=auto：探测 vector 扩展与 app.exemplar_embeddings 表，
探测不到自动走 lexical 关键词检索，不报错、不阻断启动。
向量化在 backend 内完成（调 OpenAI 兼容 embedding 接口），算法侧只收资源。
"""
from __future__ import annotations

import json
import logging
import urllib.request

import psycopg
from psycopg.rows import dict_row

from ..core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_EMBED_TIMEOUT_SECONDS = 20


def _dsn(url: str) -> str:
    """SQLAlchemy 串转 psycopg 串。"""
    return url.replace("postgresql+psycopg://", "postgresql://")


def _to_vector(values: list[float]) -> str:
    return "[" + ",".join(f"{v:.8f}" for v in values) + "]"


def detect_pgvector() -> bool:
    """探测 vector 扩展与 app.exemplar_embeddings 表是否就绪。"""
    if settings.pgvector_enabled == "off":
        return False
    if settings.pgvector_enabled == "on":
        return True
    # auto：探测（app schema 不开放给只读角色，这里用 DATABASE_URL）
    try:
        with psycopg.connect(_dsn(settings.database_url), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                if cur.fetchone() is None:
                    return False
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'app' AND table_name = 'exemplar_embeddings'"
                )
                return cur.fetchone() is not None
    except Exception as e:
        logger.warning("pgvector 探测失败，走 lexical: %s", e)
        return False


def embed_texts(texts: list[str]) -> list[list[float]]:
    """调 embedding 接口；未配置或失败返回空列表，不抛错。"""
    if not texts or not settings.embedding_api_key or not settings.embedding_base_url:
        logger.warning("embedding 未配置，跳过向量化")
        return []
    url = settings.embedding_base_url.rstrip("/") + "/embeddings"
    payload = {
        "model": settings.embedding_model,
        "input": texts,
        "dimensions": settings.embed_dim,
        "encoding_format": "float",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.embedding_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=_EMBED_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        data = body.get("data") or []
        return [item["embedding"] for item in sorted(data, key=lambda d: d.get("index", 0))]
    except Exception as e:
        logger.warning("embedding 调用失败: %s", e)
        return []


def vector_search(question: str, top_k: int = 5) -> list[dict]:
    """按问题原文走向量检索；任何异常返回空列表，由调用方降级。"""
    if not question:
        return []
    embeddings = embed_texts([question])
    if not embeddings:
        return []
    vec = embeddings[0]
    if len(vec) != settings.embed_dim:
        logger.warning("向量维度不符：期望 %s，实际 %s", settings.embed_dim, len(vec))
        return []
    literal = _to_vector(vec)
    try:
        with psycopg.connect(_dsn(settings.database_url), autocommit=True) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT exemplar_id, question,
                           1 - (embedding <=> %s::vector) AS score
                    FROM app.exemplar_embeddings
                    WHERE model = %s AND dim = %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (literal, settings.embedding_model, settings.embed_dim, literal, top_k),
                )
                return cur.fetchall()
    except Exception as e:
        logger.warning("向量检索失败，降级 lexical: %s", e)
        return []


def lexical_search(question: str, exemplars: list[dict], top_k: int = 5) -> list[dict]:
    """关键词匹配检索（pgvector 不可用时的降级方案）。"""
    if not question or not exemplars:
        return []
    keywords = [w for w in question.lower().split() if len(w) > 1]
    scored = []
    for ex in exemplars:
        ex_text = (ex.get("question") or "").lower()
        score = sum(1 for kw in keywords if kw in ex_text)
        if score > 0:
            scored.append((score, ex))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [ex for _, ex in scored[:top_k]]
