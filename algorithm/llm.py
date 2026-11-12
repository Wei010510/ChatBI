"""LiteLLM 统一封装：chat_json / chat_text / embed。

- 真实模式走 LiteLLM（OpenAI 兼容）；
- 测试模式（USE_MOCK_LLM=true）走 MockLLM，按消息前缀返回预设响应，保证单测可复现。
"""
import json
import os
from typing import Any

# 避免 LiteLLM 启动时拉取远程 cost map（网络不通时会阻塞数秒）
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

from .config import settings


def _resolve_model(model: str) -> str:
    """LiteLLM 需要 provider 前缀；配置里只写厂商真实模型名。"""
    return model if "/" in model else f"openai/{model}"


class MockLLM:
    """预置响应的 LLM Mock。按对话角色返回固定 JSON/文本。"""

    def __init__(self, responses: dict[str, Any] | None = None):
        # responses: { "understand": {...}, "plan": {...}, "coder": "SELECT ...", "writer": "..." }
        self._responses = responses or {}
        self.calls: list[dict] = []

    def _key_for(self, messages: list[dict]) -> str:
        # 优先按 S 步骤号匹配（system prompt 中含 S1/S4/S5/S8）
        text = " ".join(m.get("content", "") for m in messages)
        if "S5" in text or "Coder" in text:
            return "coder"
        if "S1" in text or "理解" in text:
            return "understand"
        if "S4" in text or "规划" in text:
            return "plan"
        if "S8" in text or "Writer" in text:
            return "writer"
        return "default"

    def chat_json(self, model, messages, temperature=0) -> dict:
        self.calls.append({"model": model, "messages": messages})
        key = self._key_for(messages)
        resp = self._responses.get(key, {})
        if isinstance(resp, str):
            try:
                return json.loads(resp)
            except Exception:
                return {}
        return dict(resp)

    def chat_text(self, model, messages, temperature=0) -> str:
        self.calls.append({"model": model, "messages": messages})
        key = self._key_for(messages)
        resp = self._responses.get(key, "")
        return resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)


# 全局 MockLLM 实例（测试时通过 set_mock_responses 配置）
_mock_llm = MockLLM()


def set_mock_responses(responses: dict[str, Any]) -> None:
    """测试用：配置 MockLLM 的预置响应。"""
    global _mock_llm
    _mock_llm = MockLLM(responses)


def get_mock_llm() -> MockLLM:
    return _mock_llm


def chat_json(model: str, messages: list[dict], temperature: float = 0) -> dict:
    """结构化 JSON 输出。非法 JSON 返回空 dict（不抛到链路外层）。"""
    if settings.use_mock_llm:
        return _mock_llm.chat_json(model, messages, temperature)
    try:
        import litellm
        resp = litellm.completion(
            model=_resolve_model(model),
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
            api_base=settings.llm_base_url or None,
            api_key=settings.llm_api_key or None,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)
    except Exception:
        return {}


def chat_text(model: str, messages: list[dict], temperature: float = 0) -> str:
    if settings.use_mock_llm:
        return _mock_llm.chat_text(model, messages, temperature)
    try:
        import litellm
        resp = litellm.completion(
            model=_resolve_model(model), messages=messages, temperature=temperature,
            api_base=settings.llm_base_url or None,
            api_key=settings.llm_api_key or None,
        )
        return resp.choices[0].message.content or ""
    except Exception:
        return ""
