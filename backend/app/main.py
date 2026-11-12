"""FastAPI 入口（SDD FR-1 / §6.3）。

注册路由、异常处理器、lifespan（建表 / L0 预热 / pgvector 探测 / 只读角色自检）。
"""
import os
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .core.exceptions import (
    AppException,
    app_exception_handler,
    unhandled_exception_handler,
)
from .core.logging import setup_logging, trace_id_var
from .query.introspection import L0LoadError, PgIntrospector
from .resources.retrieval import detect_pgvector
from .storage.session import init_db

settings = get_settings()


def _export_llm_env() -> None:
    """把 Settings 里的模型配置回填到进程环境变量。

    algorithm/config.py 用 os.getenv 读取配置，而 pydantic 的 .env 只进 Settings
    对象、不写 os.environ；这里做一次桥接，算法侧无需 import 后端。
    """
    mapping = {
        "LLM_BASE_URL": settings.llm_base_url,
        "LLM_API_KEY": settings.llm_api_key,
        "MODEL_SMALL": settings.model_small,
        "MODEL_STRONG": settings.model_strong,
        "MODEL_MID": settings.model_mid,
        "EMBEDDING_BASE_URL": settings.embedding_base_url,
        "EMBEDDING_API_KEY": settings.embedding_api_key,
        "EMBED_MODEL": settings.embedding_model,
        "EMBED_DIM": str(settings.embed_dim),
        "USE_MOCK_LLM": "true" if settings.use_mock_llm else "false",
    }
    for key, value in mapping.items():
        if value and not os.environ.get(key):
            os.environ[key] = value


# 必须在导入 algorithm 之前执行（algorithm/config.py 在 import 时读 os.getenv）
_export_llm_env()


def _check_readonly_role() -> None:
    """启动自检：DATABASE_RO_URL 角色必须是只读（SDD FR-22 / AC-19）。"""
    try:
        with psycopg.connect(settings.database_ro_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                # 尝试写操作，应失败
                try:
                    cur.execute("CREATE TABLE IF NOT EXISTS data.__ro_test (id int)")
                    raise RuntimeError("只读角色拥有写权限，启动拒绝")
                except psycopg.errors.InsufficientPrivilege:
                    pass  # 预期：权限不足
    except psycopg.errors.InsufficientPrivilege:
        pass  # 连接本身就因权限不足而失败也算只读
    except RuntimeError:
        raise
    except Exception as e:
        # 连接失败等其他错误不阻断（开发环境可能没库）
        import logging

        logging.getLogger(__name__).warning("只读角色自检跳过: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # 1. 建 app schema 表
    init_db()
    # 2. 只读角色自检
    _check_readonly_role()
    # 3. L0 introspection 预热（硬依赖，失败则启动失败）
    try:
        introspector = PgIntrospector()
        introspector.l0()
    except L0LoadError as e:
        raise RuntimeError(f"L0 元数据加载失败，服务无法启动: {e}") from e
    # 4. pgvector 探测（缺则走 lexical，不阻断）
    pgv = detect_pgvector()
    import logging

    logging.getLogger(__name__).info("pgvector enabled: %s", pgv)
    yield


app = FastAPI(title="ChatBI Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 异常处理器
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

# trace_id 中间件
@app.middleware("http")
async def set_trace_id(request, call_next):
    import uuid

    trace_id_var.set(uuid.uuid4().hex[:16])
    response = await call_next(request)
    return response


# 注册路由（统一前缀 /api）
from .api import chat, health, reports, sessions  # noqa: E402

app.include_router(health.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
