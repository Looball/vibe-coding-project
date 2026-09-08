"""API 模型校验测试（离线）。"""
import pytest
from pydantic import ValidationError

from app.api.schemas import ChatResponse, QueryRequest, SourceOut


def test_query_request_valid():
    req = QueryRequest(query="什么是大语言模型", subject="ai")
    assert req.subject == "ai"


def test_query_empty_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(query="")


def test_query_too_long_rejected():
    with pytest.raises(ValidationError):
        QueryRequest(query="x" * 2001)


def test_subject_optional():
    assert QueryRequest(query="你好").subject is None


def test_chat_response_build():
    resp = ChatResponse(
        answer="回答内容",
        sources=[SourceOut(title="LLM基础知识", page=1, score=0.76)],
        greeting=False,
    )
    assert resp.sources[0].title == "LLM基础知识"
    assert resp.sources[0].page == 1
