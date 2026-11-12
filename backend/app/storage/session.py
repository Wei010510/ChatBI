"""SQLAlchemy engine + sessionmaker（SDD §4）。

应用读写走 DATABASE_URL；QueryRunner 走 DATABASE_RO_URL（独立连接）。
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from ..core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # 云端 Postgres（Supabase）会主动断开空闲连接：定期回收 + 限制池大小，减少重连抖动
    pool_recycle=180,
    pool_size=5,
    max_overflow=5,
    pool_timeout=10,
    # 远程库建连慢/可能失联：给建连设上限，避免请求一直挂着
    connect_args={"connect_timeout": 10},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

Base = declarative_base()


def init_db() -> None:
    """建 app schema 所有表。"""
    from . import models  # noqa: F401  确保模型注册

    Base.metadata.create_all(bind=engine)
