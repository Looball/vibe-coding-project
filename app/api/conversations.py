"""会话管理接口：创建/列表/历史/发送消息/清除（MySQL 持久化）。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.schemas import (
    ChatResponse,
    ConversationCreate,
    ConversationOut,
    MessageHistoryOut,
    MessageOut,
    MessageSend,
)
from app.db.mysql import get_db
from app.models.mysql_models import Conversation, Message, MessageRole
from app.services import qa

router = APIRouter(prefix="/conversations", tags=["conversations"])


def _get_conversation(db: Session, cid: str) -> Conversation:
    conv = db.get(Conversation, cid)
    if conv is None:
        raise HTTPException(status_code=404, detail=f"会话 {cid} 不存在")
    return conv


def _answer_or_400(query: str, subject: str | None):
    try:
        return qa.answer_sync(query, subject_code=subject)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _parse_sources(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    return [s for s in raw if isinstance(s, dict)]


@router.get("", response_model=list[ConversationOut], summary="会话列表")
def list_conversations(
    limit: int = 50, db: Session = Depends(get_db)
) -> list[ConversationOut]:
    convs = db.execute(
        select(Conversation)
        .order_by(Conversation.updated_at.desc())
        .limit(max(1, min(limit, 200)))
    ).scalars().all()
    counts = dict(
        db.execute(
            select(Message.conversation_id, func.count(Message.id)).group_by(
                Message.conversation_id
            )
        ).all()
    )
    return [
        ConversationOut(
            id=c.id,
            title=c.title,
            subject_id=c.subject_id,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=counts.get(c.id, 0),
        )
        for c in convs
    ]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
def create_conversation(
    body: ConversationCreate, db: Session = Depends(get_db)
) -> ConversationOut:
    conv = Conversation(id=uuid.uuid4().hex, title=body.title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return ConversationOut(
        id=conv.id,
        title=conv.title,
        subject_id=None,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0,
    )


@router.get("/{cid}/messages", response_model=MessageHistoryOut, summary="消息历史")
def get_messages(
    cid: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> MessageHistoryOut:
    _get_conversation(db, cid)
    cap = max(1, min(limit, 200))
    msgs = db.execute(
        select(Message)
        .where(Message.conversation_id == cid)
        .order_by(Message.id.desc())
        .offset(max(0, offset))
        .limit(cap + 1)
    ).scalars().all()
    has_more = len(msgs) > cap
    msgs = msgs[:cap]
    return MessageHistoryOut(
        messages=[
            MessageOut(
                id=m.id,
                role=m.role.value if hasattr(m.role, "value") else str(m.role),
                content=m.content,
                sources=_parse_sources(m.sources),
                created_at=m.created_at,
            )
            for m in msgs
        ],
        has_more=has_more,
    )


@router.post("/{cid}/messages", response_model=ChatResponse, summary="发送消息并持久化")
def send_message(
    cid: str, body: MessageSend, db: Session = Depends(get_db)
) -> ChatResponse:
    conv = _get_conversation(db, cid)

    db.add(
        Message(conversation_id=cid, role=MessageRole.user, content=body.query)
    )

    result = _answer_or_400(body.query, body.subject)
    sources = [s.__dict__ for s in result.sources]
    db.add(
        Message(
            conversation_id=cid,
            role=MessageRole.assistant,
            content=result.text,
            sources=sources,
        )
    )
    if not conv.title:
        conv.title = body.query[:50]
    conv.updated_at = datetime.now()
    db.commit()

    return ChatResponse(
        answer=result.text, sources=sources, greeting=result.greeting
    )


@router.delete("/{cid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(cid: str, db: Session = Depends(get_db)) -> Response:
    conv = _get_conversation(db, cid)
    db.delete(conv)  # messages 级联删除
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
