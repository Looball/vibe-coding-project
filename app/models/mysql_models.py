"""MySQL ORM 模型：对应技术设计文档中的表结构。"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.mysql import Base


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class DocumentStatus(int, enum.Enum):
    pending = 0
    processed = 1
    failed = 2


class ConversationStatus(int, enum.Enum):
    closed = 0
    active = 1


# ---------- 学科知识 ----------

class Subject(Base):
    """学科表。"""

    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="学科名称")
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, comment="学科编码")
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(back_populates="subject")
    documents: Mapped[list["Document"]] = relationship(back_populates="subject")
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="subject")


class KnowledgePoint(Base):
    """知识点表（知识图谱节点，支持父子层级）。"""

    __tablename__ = "knowledge_points"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="知识点标题")
    content: Mapped[str | None] = mapped_column(Text)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_points.id"))
    level: Mapped[int] = mapped_column(default=0)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    subject: Mapped[Subject] = relationship(back_populates="knowledge_points")
    parent: Mapped["KnowledgePoint | None"] = relationship(remote_side=[id])


class Document(Base):
    """上传的原始文档记录。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_type: Mapped[str | None] = mapped_column(String(20), comment="pdf/docx/md")
    chunk_count: Mapped[int] = mapped_column(default=0, comment="切分后的分块数")
    status: Mapped[DocumentStatus] = mapped_column(default=DocumentStatus.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    subject: Mapped[Subject] = relationship(back_populates="documents")


# ---------- 会话与消息 ----------

class Conversation(Base):
    """会话表。"""

    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, comment="会话UUID")
    title: Mapped[str | None] = mapped_column(String(100))
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"))
    status: Mapped[ConversationStatus] = mapped_column(default=ConversationStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    subject: Mapped[Subject | None] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at"
    )


class Message(Base):
    """对话消息表。"""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list | None] = mapped_column(JSON, comment="引用的文档来源(JSON数组)")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
