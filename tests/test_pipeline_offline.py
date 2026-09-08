"""RAG 流程离线测试（不触发网络/LLM）。"""
from app.core.config import SUBJECT_LABELS
from app.rag.pipeline import StageResult, search, summarize
from app.rag.query_rewrite import build_rewrite_messages, rewrite_query
from app.rag.retriever import ContextBlock


def test_rewrite_messages_built_with_subject():
    msgs = build_rewrite_messages("就业课程包含什么", subject_code="ai")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert "人工智能" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "就业课程包含什么"}


def test_rewrite_disabled_returns_original(monkeypatch):
    monkeypatch.setenv("EDURAG_DISABLE_REWRITE", "1")
    assert rewrite_query("什么是大语言模型", "ai") == "什么是大语言模型"


def test_unknown_subject_falls_back_to_code_label():
    assert SUBJECT_LABELS.get("nope", "nope") == "nope"


def test_pipeline_greeting_short_circuit():
    stage = search("早上好")  # 问候走直连，不触发改写/检索
    assert stage.greeting is True
    assert stage.greeting_text is not None
    assert stage.blocks == []


def test_summarize_no_context():
    stage = StageResult(greeting=False, greeting_text=None, rewritten="q", blocks=[])
    text = summarize(stage, "原问题")
    assert "无（知识库未命中）" in text


def test_summarize_blocks():
    blocks = [
        ContextBlock(
            parent_chunk_id="abc", doc_title="文档A", page=3, text="内容", score=0.9
        )
    ]
    stage = StageResult(greeting=False, greeting_text=None, rewritten="q", blocks=blocks)
    text = summarize(stage, "原问题")
    assert "改写后" in text and "文档A" in text
