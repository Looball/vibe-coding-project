"""Parent-Child 分块器。

按 config.ini 的 [retrieval] 参数工作：
    parent_chunk_size = 1200（父块，作为最终 LLM 上下文）
    child_chunk_size  = 300 （子块，作为向量检索单位）
    chunk_overlap     = 50   （块间重叠 token 数）

策略：token 滑窗（tiktoken cl100k 近似计词）+ 固定重叠；按页处理以保留页码。
子块命中后由上层回取所属父块文本（存于 Milvus parent_text）。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

import tiktoken

from app.core.config import settings

_ENC = tiktoken.get_encoding("cl100k_base")


@dataclass
class ParentChunk:
    parent_chunk_id: str
    page: int
    text: str
    children: list[str] = field(default_factory=list)


def count_tokens(text: str) -> int:
    return len(_ENC.encode(text))


def split_by_tokens(
    text: str,
    chunk_size: int,
    overlap: int = 0,
) -> list[str]:
    """按 token 数切分，块间重叠 overlap 个 token，返回文本块列表。"""
    if not text or not text.strip():
        return []
    tokens = _ENC.encode(text)
    if len(tokens) <= chunk_size:
        return [text]

    step = chunk_size - overlap
    if step < 1:
        step = 1

    chunks: list[str] = []
    start = 0
    n = len(tokens)
    while start < n:
        end = min(start + chunk_size, n)
        chunks.append(_ENC.decode(tokens[start:end]))
        if end >= n:
            break
        start = end - overlap

    # 去重空块并合并可能因重叠产生的高度重复尾部
    cleaned: list[str] = []
    for c in chunks:
        s = c.strip()
        if s and (not cleaned or cleaned[-1] != s):
            cleaned.append(c)
    return cleaned


def chunk_pages(
    pages: list[tuple[int, str]],
    parent_size: int | None = None,
    child_size: int | None = None,
    overlap: int | None = None,
) -> list[ParentChunk]:
    """把按页文本切成 Parent-Child 两级。

    Args:
        pages: [(page_no, page_text), ...]
        parent_size/child_size/overlap: 默认取 config.ini [retrieval] 配置

    Returns:
        每个父块含唯一 id、页码、父文本与子块列表。
    """
    p_size = parent_size or settings.parent_chunk_size
    c_size = child_size or settings.child_chunk_size
    ov = overlap if overlap is not None else settings.chunk_overlap

    parents: list[ParentChunk] = []
    for page_no, page_text in pages:
        for parent_text in split_by_tokens(page_text, p_size, ov):
            children = split_by_tokens(parent_text, c_size, ov)
            parents.append(
                ParentChunk(
                    parent_chunk_id=uuid.uuid4().hex,
                    page=page_no,
                    text=parent_text,
                    children=children,
                )
            )
    return parents
