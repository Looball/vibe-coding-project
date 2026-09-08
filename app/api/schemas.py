"""API 请求/响应模型。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- 问答 ----------

class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    subject: str | None = Field(default=None, description="学科 code，如 ai/java")


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str = ""
    page: int = 0
    score: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut] = []
    greeting: bool = False


# ---------- 会话 ----------

class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=100)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str | None
    subject_id: int | None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class MessageSend(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    subject: str | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    sources: list[SourceOut] = []
    created_at: datetime


class MessageHistoryOut(BaseModel):
    messages: list[MessageOut]
    has_more: bool = False


# ---------- 元信息 ----------

class SubjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    description: str | None


class HealthOut(BaseModel):
    status: str
    services: dict[str, str]
