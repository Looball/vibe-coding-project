"""阿里云 DashScope 模型客户端：LLM 对话 + 文本嵌入。

所有模型均走 OpenAI 兼容接口（config.ini 的 [llm] 节）：
    base_url : dashscope_base_url
    LLM     : qwen3.6-plus
    嵌入    : text-embedding-v3 (在线调用, 1024 维)

API Key 通过环境变量 DASHSCOPE_API_KEY 注入（见 config.py）。
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import Any

from openai import AsyncOpenAI, OpenAI

from app.core.config import settings


class DashScopeClient:
    """封装同步/异步 LLM 调用与文本嵌入。"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
    ) -> None:
        self.model = model or settings.llm_model
        self.embedding_model = embedding_model or settings.embedding_model
        api_key = api_key or settings.dashscope_api_key
        base_url = base_url or settings.dashscope_base_url

        self._sync = OpenAI(api_key=api_key, base_url=base_url)
        self._async = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # ---------- LLM 对话 ----------

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """一次性返回完整回答。"""
        resp = self._sync.chat.completions.create(
            model=self.model, messages=messages, stream=False, **kwargs
        )
        return resp.choices[0].message.content or ""

    def chat_stream(self, messages: list[dict[str, str]], **kwargs: Any) -> Iterator[str]:
        """同步流式返回回答片段（适用于命令行调试）。"""
        stream = self._sync.chat.completions.create(
            model=self.model, messages=messages, stream=True, **kwargs
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    async def achat_stream(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> AsyncIterator[str]:
        """异步流式返回回答片段（适用于 FastAPI SSE 接口）。"""
        stream = await self._async.chat.completions.create(
            model=self.model, messages=messages, stream=True, **kwargs
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    # ---------- 文本嵌入 ----------

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入，返回与输入顺序一致的长度 EMBEDDING_DIM 向量列表。"""
        resp = self._sync.embeddings.create(model=self.embedding_model, input=texts)
        ordered = sorted(resp.data, key=lambda d: d.index)
        return [d.embedding for d in ordered]

    def embed_text(self, text: str) -> list[float]:
        """单条文本嵌入（用于检索 Query 向量化）。"""
        return self.embed_texts([text])[0]

    # ---------- 便捷构建 ----------

    @staticmethod
    def system_prompt(text: str) -> dict[str, str]:
        return {"role": "system", "content": text}

    @staticmethod
    def user_message(text: str) -> dict[str, str]:
        return {"role": "user", "content": text}


_instance: DashScopeClient | None = None


def get_client() -> DashScopeClient:
    """获取全局 DashScopeClient（延迟实例化，进程内单例）。"""
    global _instance
    if _instance is None:
        _instance = DashScopeClient()
    return _instance
