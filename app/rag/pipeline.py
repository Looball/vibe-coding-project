"""RAG 核心流程编排：query 理解 → 改写 → 混合检索 → 聚合重排 → 上下文。

流程（对应技术设计文档 2.1）：
    问候语识别 → (可选)LLM Query 改写
    → 稠密嵌入 + 混合检索(Milvus dense + BM25/jieba, RRF 融合)
    → 子块按 parent_chunk_id 去重、取最高分 → 排序取 candidate_m 父块(重排)
    → 返回上下文块，由调用方拼 Prompt 并生成。

CLI 演示：
    uv run python -m app.rag.pipeline "什么是大语言模型" --subject ai
"""
from __future__ import annotations

from dataclasses import dataclass

from app.rag.greeting import detect_greeting
from app.rag.query_rewrite import rewrite_query
from app.rag.retriever import ContextBlock, retrieve


@dataclass
class StageResult:
    greeting: bool
    greeting_text: str | None
    rewritten: str
    blocks: list[ContextBlock]


def search(query: str, subject_code: str | None = None, rewrite: bool = True) -> StageResult:
    """执行 RAG 前四阶段，返回问候信息/改写结果/重排后上下文。"""
    greeting = detect_greeting(query)
    if greeting:
        return StageResult(greeting=True, greeting_text=greeting, rewritten=query, blocks=[])

    rewritten = rewrite_query(query, subject_code) if rewrite else query.strip()
    blocks = retrieve(rewritten, subject_code=subject_code)
    return StageResult(greeting=False, greeting_text=None, rewritten=rewritten, blocks=blocks)


def summarize(stage: StageResult, query: str) -> str:
    """把阶段结果压成可读文本（诊断/日志用）。"""
    if stage.greeting:
        return f"问候语命中，直接回复：{stage.greeting_text}"
    lines = [f"改写前: {query}", f"改写后: {stage.rewritten or '(未改写)'}"]
    if not stage.blocks:
        lines.append("召回: 无（知识库未命中）")
        return "\n".join(lines)
    lines.append(f"召回并重排 Top{len(stage.blocks)} 父块:")
    for i, b in enumerate(stage.blocks, 1):
        lines.append(f"  {i}. [{b.score:.4f}]《{b.doc_title}》第{b.page}页 父块id={b.parent_chunk_id[:8]}")
    return "\n".join(lines)


def __main_cli() -> None:
    import argparse

    from app.clients.dashscope import get_client
    from app.core.config import subject_label

    parser = argparse.ArgumentParser(description="RAG 核心流程演示")
    parser.add_argument("query", help="要问的问题")
    parser.add_argument("--subject", default=None, help="学科 code，如 ai")
    parser.add_argument("--no-rewrite", action="store_true", help="关闭 LLM Query 改写")
    args = parser.parse_args()

    stage = search(args.query, args.subject, rewrite=not args.no_rewrite)
    print("== RAG 流程 ==")
    print(summarize(stage, args.query))
    if stage.greeting:
        return

    from app.rag.retriever import format_context as _fmt

    if not stage.blocks:
        print("\n回答: 抱歉，知识库未找到相关内容。")
        return
    system = (
        f"你是一个{subject_label(args.subject)}学科的智能助教，请基于参考资料回答学生问题。"
        "若资料与问题无关，请如实告知。要求简洁、准确、条理清晰，可注明资料编号，使用中文。"
    )
    messages = [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": f"参考资料：\n{_fmt(stage.blocks)}\n\n学生问题：{args.query}\n\n请回答：",
        },
    ]
    print("\n回答:")
    print(get_client().chat(messages))


if __name__ == "__main__":
    __main_cli()
