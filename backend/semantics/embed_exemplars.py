"""把 exemplars.yaml 的问句写成向量（第 4 轮）。

用法（在 backend 目录）：
    python -m semantics.embed_exemplars

行为：
- 只对 question 文本做 embedding，SQL 不进向量；
- 按 content_hash 跳过未变更的示例，支持增量重跑；
- 维度必须等于 EMBED_DIM，否则整批跳过并报错；
- 单条失败重试一次，仍失败则记入失败清单，其余照常写入。
"""
from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path

import psycopg
import yaml

from app.core.config import get_settings
from app.resources.retrieval import _dsn, embed_texts

logger = logging.getLogger(__name__)
settings = get_settings()

_SEMANTICS_DIR = Path(__file__).resolve().parent
_BATCH_SIZE = 32

_UPSERT_SQL = """
INSERT INTO app.exemplar_embeddings
    (exemplar_id, question, embedding, model, dim, content_hash, updated_at)
VALUES (%s, %s, %s::vector, %s, %s, %s, NOW())
ON CONFLICT (exemplar_id, model) DO UPDATE
SET question = EXCLUDED.question,
    embedding = EXCLUDED.embedding,
    dim = EXCLUDED.dim,
    content_hash = EXCLUDED.content_hash,
    updated_at = NOW()
"""


def _content_hash(question: str) -> str:
    return hashlib.sha256(question.strip().encode("utf-8")).hexdigest()[:16]


def _load_exemplars() -> list[dict]:
    path = _SEMANTICS_DIR / "exemplars.yaml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    items = data.get("exemplars") or []
    return [item for item in items if isinstance(item, dict) and item.get("id") and item.get("question")]


def _existing_hashes(conn) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT exemplar_id, content_hash FROM app.exemplar_embeddings WHERE model = %s",
            (settings.embedding_model,),
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def _embed_batch(texts: list[str]) -> list[list[float]]:
    vectors = embed_texts(texts)
    if vectors:
        return vectors
    logger.warning("首批向量化失败，重试一次")
    return embed_texts(texts)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not settings.embedding_api_key or not settings.embedding_base_url:
        print("缺少 EMBEDDING_BASE_URL / EMBEDDING_API_KEY，无法向量化", file=sys.stderr)
        return 1

    exemplars = _load_exemplars()
    if not exemplars:
        print("exemplars.yaml 没有可用示例", file=sys.stderr)
        return 1

    with psycopg.connect(_dsn(settings.database_url)) as conn:
        try:
            existing = _existing_hashes(conn)
        except psycopg.errors.UndefinedTable:
            print("app.exemplar_embeddings 不存在，请先执行 infra/init.sql 第 6 节", file=sys.stderr)
            return 1

        pending = [
            ex for ex in exemplars
            if existing.get(str(ex["id"])) != _content_hash(str(ex["question"]))
        ]
        print(f"示例总数 {len(exemplars)}，待向量化 {len(pending)}（未变更 {len(exemplars) - len(pending)}）")
        if not pending:
            return 0

        written = 0
        failed: list[str] = []
        for start in range(0, len(pending), _BATCH_SIZE):
            batch = pending[start:start + _BATCH_SIZE]
            vectors = _embed_batch([str(ex["question"]) for ex in batch])
            if not vectors or len(vectors) != len(batch):
                failed.extend(str(ex["id"]) for ex in batch)
                logger.error("批次 %s 向量化失败", start // _BATCH_SIZE)
                continue
            rows = []
            for ex, vec in zip(batch, vectors):
                if len(vec) != settings.embed_dim:
                    logger.error("%s 维度 %s != EMBED_DIM %s", ex["id"], len(vec), settings.embed_dim)
                    failed.append(str(ex["id"]))
                    continue
                rows.append((
                    str(ex["id"]),
                    str(ex["question"]),
                    "[" + ",".join(f"{v:.8f}" for v in vec) + "]",
                    settings.embedding_model,
                    settings.embed_dim,
                    _content_hash(str(ex["question"])),
                ))
            if rows:
                with conn.cursor() as cur:
                    cur.executemany(_UPSERT_SQL, rows)
                conn.commit()
                written += len(rows)

    print(f"写入 {written} 条，模型 {settings.embedding_model}，维度 {settings.embed_dim}")
    if failed:
        print("失败：" + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
