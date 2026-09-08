"""问答生成层：调用 RAG 流程编排(pipeline)取上下文，再拼 Prompt 走 DashScope LLM。

即时回答 answer_sync()；流式（SSE）answer_stream()。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.clients.dashscope import get_client
from app.core.config import SUBJECT_LABELS, subject_label
from app.rag.pipeline import search
from app.rag.retriever import ContextBlock, format_context

_NO_CONTEXT_MSG = "抱歉，我暂未在知识库中找到与这个问题直接相关的资料。可以换一种问法，或换个学科试试。"


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


def _messages_for(
    question: str, blocks: list[ContextBlock], subject_code: str | None
) -> list[dict[str, str]]:
    system = (
        f"你是一个{subject_label(subject_code)}学科的智能助教，请基于以下参考资料回答学生的问题。"
        "若参考资料与问题无关，请如实告知“暂未找到相关答案”，不要编造。"
        "回答要求：简洁、准确、条理清晰；如需引用，注明对应资料编号；使用中文。"
    )
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


def _validate(subject_code: str | None) -> None:
    if subject_code and subject_code not in SUBJECT_LABELS:
        raise ValueError(f"subject '{subject_code}' 不在支持范围 {list(SUBJECT_LABELS)}")


def answer_sync(
    question: str, subject_code: str | None = None, rewrite: bool = True
) -> AnswerResult:
    """即时返回完整回答。"""
    _validate(subject_code)
    stage = search(question, subject_code, rewrite=rewrite)
    if stage.greeting:
        return AnswerResult(text=stage.greeting_text or "", sources=[], greeting=True)
    if not stage.blocks:
        return AnswerResult(text=_NO_CONTEXT_MSG, sources=[], greeting=False)

    text = get_client().chat(_messages_for(question, stage.blocks, subject_code))
    sources = [
        SourceRef(title=b.doc_title, page=b.page, score=b.score) for b in stage.blocks
    ]
    return AnswerResult(text=text, sources=sources, greeting=False)


async def answer_stream(
    question: str, subject_code: str | None = None, rewrite: bool = True
) -> AsyncIterator[dict]:
    """流式回答：先发 sources 事件，再逐 token，最后 done。"""
    _validate(subject_code)
    stage = search(question, subject_code, rewrite=rewrite)
    if stage.greeting:
        yield {"type": "sources", "sources": []}
        yield {"type": "token", "content": stage.greeting_text or ""}
        yield {"type": "done"}
        return
    if not stage.blocks:
        yield {"type": "sources", "sources": []}
        yield {"type": "token", "content": _NO_CONTEXT_MSG}
        yield {"type": "done"}
        return

    yield {
        "type": "sources",
        "sources": [
            {"title": b.doc_title, "page": b.page, "score": b.score}
            for b in stage.blocks
        ],
    }
    async for token in get_client().achat_stream(
        _messages_for(question, stage.blocks, subject_code)
    ):
        yield {"type": "token", "content": token}
    yield {"type": "done"}
