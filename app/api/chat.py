"""问答接口：即时回答 + 流式回答(SSE)。"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from app.api.schemas import ChatResponse, QueryRequest
from app.services import qa

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, summary="即时回答")
async def chat(req: QueryRequest) -> ChatResponse:
    result = qa.answer_sync(req.query, subject_code=req.subject)
    return ChatResponse(
        answer=result.text,
        sources=[s.__dict__ for s in result.sources],
        greeting=result.greeting,
    )


async def _sse_events(query: str, subject: str | None) -> AsyncIterator[dict]:
    """把 qa.answer_stream 事件映射为 SSE 事件。"""
    async for ev in qa.answer_stream(query, subject_code=subject):
        if ev["type"] == "sources":
            yield {
                "event": "sources",
                "data": json.dumps([s.__dict__ for s in ev["sources"]], ensure_ascii=False),
            }
        elif ev["type"] == "token":
            yield {"event": "message", "data": ev["content"]}
        else:  # done
            yield {"event": "done", "data": ""}


@router.post("/stream", summary="流式回答(SSE)")
async def chat_stream(req: QueryRequest) -> EventSourceResponse:
    return EventSourceResponse(_sse_events(req.query, req.subject))
