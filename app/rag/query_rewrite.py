"""Query 改写（RAG 流程第一阶段：查询理解/改写）。

把用户口语化、指代不清的提问改写为更适合向量检索的自包含查询。
可用环境变量 EDURAG_DISABLE_REWRITE=1 关闭（离线/调试用）。
"""
from __future__ import annotations

import os

from app.clients.dashscope import get_client
from app.core.config import subject_label

_REWRITE_SYSTEM = (
    "你是{subject}学科的检索查询改写器。请把学生的问题改写为"
    "一个自包含、适合向量检索的查询（可补全指代、展开缩写、去口语），"
    "不要改变原意，不要作答。只输出改写后的查询本身，不超过 60 字。"
)


def build_rewrite_messages(query: str, subject_code: str | None) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": _REWRITE_SYSTEM.format(subject=subject_label(subject_code))},
        {"role": "user", "content": query},
    ]


def rewrite_query(query: str, subject_code: str | None = None) -> str:
    """LLM 改写查询；关闭开关或失败时原样返回。"""
    if os.environ.get("EDURAG_DISABLE_REWRITE", "").strip() not in ("", "0"):
        return query.strip()
    try:
        rewritten = get_client().chat(build_rewrite_messages(query, subject_code)).strip()
        return rewritten or query.strip()
    except Exception:
        return query.strip()
