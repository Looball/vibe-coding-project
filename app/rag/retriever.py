"""检索器：query 向量化 → Milvus 检索 → 按父块去重聚合为上下文。

检索子块（child）向量，命中后按 parent_chunk_id 去重：每个父块取最高子分，
再按分排序取 Top candidate_m 作为最终上下文（对应 config.ini [retrieval]）。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.clients.dashscope import get_client as get_llm_client
from app.core.config import settings
from app.db.milvus import get_store


@dataclass
class ContextBlock:
    """送入 LLM 的一个知识上下文（父块）。"""
    parent_chunk_id: str
    doc_title: str
    page: int
    text: str
    score: float


def retrieve(
    query: str,
    subject_code: str | None = None,
    top_k: int | None = None,
    candidate_m: int | None = None,
) -> list[ContextBlock]:
    """检索给定问题最相关的 candidate_m 个父块。

    Args:
        query: 用户问题
        subject_code: 学科过滤，None 表示全部学科
        top_k: Milvus 返回子块候选数，默认 retrieval_k
        candidate_m: 最终取几个父块，默认 candidate_m
    """
    k = top_k or settings.retrieval_k
    m = candidate_m or settings.candidate_m

    query_vec = get_llm_client().embed_text(query)
    hits = get_store().search(query_vec, subject_code=subject_code, limit=k)

    # 按父块去重，保留每个父块内最高相似度的子块
    best: dict[str, ContextBlock] = {}
    for h in hits:
        cur = best.get(h.parent_chunk_id)
        if cur is None or h.score > cur.score:
            best[h.parent_chunk_id] = ContextBlock(
                parent_chunk_id=h.parent_chunk_id,
                doc_title=h.doc_title,
                page=h.page,
                text=h.parent_text or h.chunk_text,
                score=h.score,
            )

    ranked = sorted(best.values(), key=lambda b: b.score, reverse=True)
    return ranked[:m]


def format_context(blocks: list[ContextBlock]) -> str:
    """把上下文块拼成带出处编号的文本，供 Prompt 使用。"""
    parts = []
    for i, b in enumerate(blocks, start=1):
        header = f"资料{i}"
        if b.doc_title:
            header += f"《{b.doc_title}》"
        if b.page:
            header += f" 第{b.page}页"
        parts.append(f"{header}\n{b.text.strip()}")
    return "\n\n".join(parts)
