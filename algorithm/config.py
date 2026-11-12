"""算法模块配置：从环境变量读取，提供默认值。

模型档位按任务区分：S1/S4 小模型、S5 强模型、S8 中档、Embedding 独立。
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # LLM 三元组（OpenAI 兼容）
    llm_base_url: str = os.getenv("LLM_BASE_URL", "")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    model_small: str = os.getenv("MODEL_SMALL", "gpt-4o-mini")
    model_strong: str = os.getenv("MODEL_STRONG", "gpt-4o")
    model_mid: str = os.getenv("MODEL_MID", "gpt-4o-mini")

    # Embedding
    embedding_base_url: str = os.getenv("EMBEDDING_BASE_URL", "")
    embedding_api_key: str = os.getenv("EMBEDDING_API_KEY", "")
    embed_model: str = os.getenv("EMBED_MODEL", "text-embedding-3-small")

    # 执行参数
    sql_timeout_ms: int = int(os.getenv("SQL_TIMEOUT_MS", "5000"))
    max_rows: int = int(os.getenv("MAX_ROWS", "1000"))

    # 测试开关：为 true 时使用 MockLLM，不发起真实网络请求
    use_mock_llm: bool = os.getenv("USE_MOCK_LLM", "true").lower() in ("1", "true", "yes")


settings = Settings()
