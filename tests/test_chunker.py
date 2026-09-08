"""chunker 单元测试（离线）。"""
import pytest

from app.core.config import settings
from app.rag.chunker import chunk_pages, count_tokens, split_by_tokens


class TestSplitByTokens:
    def test_short_text_single_chunk(self):
        assert split_by_tokens("你好世界", 300) == ["你好世界"]

    def test_empty_or_blank_returns_nothing(self):
        assert split_by_tokens("", 300) == []
        assert split_by_tokens("   \n ", 300) == []

    def test_chunk_never_exceeds_size(self):
        text = "大语言模型（LLM）是人工智能模型。" * 200  # 远超单块
        for chunk in split_by_tokens(text, chunk_size=300, overlap=0):
            assert count_tokens(chunk) <= 300

    def test_overlap_increases_chunk_count(self):
        text = "这是用于切分测试的一段中文文本。" * 120
        no_overlap = split_by_tokens(text, chunk_size=200, overlap=0)
        overlap = split_by_tokens(text, chunk_size=200, overlap=50)
        assert len(overlap) >= len(no_overlap) >= 1


class TestChunkPages:
    def test_single_page_produces_parents_with_children(self):
        text = "大语言模型的发展经历了从统计语言模型到神经语言模型的演进。" * 150
        parents = chunk_pages([(1, text)])
        assert parents
        for p in parents:
            assert p.page == 1
            assert p.text.strip()
            assert p.children
            assert count_tokens(p.text) <= settings.parent_chunk_size
            for child in p.children:
                assert count_tokens(child) <= settings.child_chunk_size

    def test_page_number_is_carried(self):
        pages = [(1, "这是第一页内容。"), (2, "这是第二页内容。")]
        parents = chunk_pages(pages)
        assert {p.page for p in parents} == {1, 2}

    def test_tiny_text_yields_one_parent(self):
        parents = chunk_pages([(0, "仅有一句。" * 3)])
        assert len(parents) == 1
        assert len(parents[0].children) == 1
