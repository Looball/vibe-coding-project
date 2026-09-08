"""问答编排服务：问候语识别 + RAG 检索 → Prompt → DashScope LLM 生成。

即时回答用 answer_sync()；流式（SSE）用 answer_stream()。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.clients.dashscope import get_client
from app.core.config import settings
from app.rag.greeting import detect_greeting
from app.rag.retriever import ContextBlock, format_context, retrieve

SUBJECT_LABELS = {
    "ai": "人工智能",
    "java": "Java",
    "test": "软件测试",
    "ops": "运维",
    "bigdata": "大数据",
}

_SYSTEM_TMPL = (
    "你是一个{subject}学科的智能助教，请基于以下参考资料回答学生的问题。"
    "若参考资料与问题无关，请如实告知“暂未找到相关答案”，不要编造。"
    "回答要求：简洁、准确、条理清晰；如需引用，注明对应资料编号；使用中文。"
)
_NO_CONTEXT_MSG = "抱歉，我暂未在知识库中找到与这个问题直接相关的资料。可以换一种问法，或换个学科试试。"
_GREETING_FALLBACK = "你好呀！我是智能助教，欢迎提问～"


@dataclass
class SourceRef:
    title: str
    page: int
    score: float


@dataclass
class AnswerResult:
    text: str
    sources: list[SourceRef]
    greeting: bool


def _subject_label(subject_code: str | None) -> str:
    if not subject_code:
        return "通用"
    return SUBJECT_LABELS.get(subject_code, subject_code)


def _messages_for(
    question: str, blocks: list[ContextBlock], subject_code: str | None
) -> list[dict[str, str]]:
    system = _SYSTEM_TMPL.format(subject=_subject_label(subject_code))
    user = (
        "参考资料：\n"
        f"{format_context(blocks)}\n\n"
        f"学生问题：{question}\n\n"
        "请回答："
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _sources(blocks: list[ContextBlock]) -> list[SourceRef]:
    return [
        SourceRef(title=b.doc_title, page=b.page, score=b.score) for b in blocks
    ]


def answer_sync(question: str, subject_code: str | None = None) -> AnswerResult:
    """即时返回完整回答。"""
    if subject_code and subject_code not in SUBJECT_LABELS:
        raise ValueError(
            f"subject '{subject_code}' 不在支持范围 {list(SUBJECT_LABELS)}"
        )

    greeting = detect_greeting(question)
    if greeting:
        return AnswerResult(text=greeting, sources=[], greeting=True)

    blocks = retrieve(question, subject_code=subject_code)
    if not blocks:
        return AnswerResult(text=_NO_CONTEXT_MSG, sources=[], greeting=False)

    text = get_client().chat(_messages_for(question, blocks, subject_code))
    return AnswerResult(text=text, sources=_sources(blocks), greeting=False)


async def answer_stream(
    question: str, subject_code: str | None = None
) -> AsyncIterator[dict]:
    """流式回答：先发 sources 事件，再逐 token，最后 done。"""
    if subject_code and subject_code not in SUBJECT_LABELS:
        raise ValueError(
            f"subject '{subject_code}' 不在支持范围 {list(SUBJECT_LABELS)}"
        )

    greeting = detect_greeting(question)
    if greeting:
        yield {"type": "sources", "sources": []}
        yield {"type": "token", "content": greeting}
        yield {"type": "done"}
        return

    blocks = retrieve(question, subject_code=subject_code)
    if not blocks:
        yield {"type": "sources", "sources": []}
        yield {"type": "token", "content": _NO_CONTEXT_MSG}
        yield {"type": "done"}
        return

    yield {"type": "sources", "sources": _sources(blocks)}
    async for token in get_client().achat_stream(
        _messages_for(question, blocks, subject_code)
    ):
        yield {"type": "token", "content": token}
    yield {"type": "done"}
