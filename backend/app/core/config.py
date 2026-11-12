"""配置：从环境变量读取（SDD FR-2 / §6.2）。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 数据库
    database_url: str = "postgresql+psycopg://chatbi:chatbi@localhost:5432/chatbi"
    database_ro_url: str = "postgresql+psycopg://chatbi_ro:chatbi_ro@localhost:5432/chatbi"
    database_meta_url: str = ""  # 缺省回落 DATABASE_RO_URL

    # LLM（OpenAI 兼容）：三档模型名供算法侧 os.getenv 读取
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    model_small: str = "qwen3.8-flash"
    model_strong: str = "qwen3.8-flash"
    model_mid: str = "qwen3.8-flash"
    # true 时算法走 MockLLM，不发真实请求；单测保持 true，本地联调置 false
    use_mock_llm: bool = True

    # Embedding
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "qwen3.7-text-embedding"
    embed_dim: int = 1024

    # 执行与检索
    query_timeout_ms: int = 5000
    max_rows: int = 1000
    cache_ttl_seconds: int = 604800  # 7 天
    pgvector_enabled: str = "auto"  # auto | on | off

    @property
    def effective_meta_url(self) -> str:
        return self.database_meta_url or self.database_ro_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
