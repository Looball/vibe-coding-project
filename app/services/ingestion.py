"""语料入库服务：解析 → Parent-Child 分块 → DashScope 嵌入 → 写 Milvus + MySQL。

用法:
    uv run python -m app.services.ingestion \
        --dir documents/data/ai_data --subject ai [--reset]

前置条件:
    - MySQL / Milvus 在线（config.ini 指定库/集合）
    - .env 提供真实 DASHSCOPE_API_KEY（在线嵌入，按量计费）
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from sqlalchemy import delete, select

from app.clients.dashscope import get_client as get_llm_client
from app.core.config import settings
from app.db.milvus import EMBEDDING_DIM, MilvusStore, get_store
from app.db.mysql import SessionLocal, init_db
from app.models.mysql_models import (
    Document,
    DocumentStatus,
    Subject,
)
from app.rag.chunker import chunk_pages
from app.rag.document_loader import RawDocument, load_dir, load_file

SUBJECT_NAMES = {
    "ai": "人工智能",
    "java": "Java 开发",
    "test": "软件测试",
    "ops": "运维",
    "bigdata": "大数据",
}

# 单次嵌入请求的文本数上限（text-embedding-v3 对 batch/token 有配额，超限自适应减半）
EMBED_BATCH = 8


def seed_subjects(db) -> dict[str, int]:
    """写入学科种子数据，返回 code -> id 映射。"""
    result: dict[str, int] = {}
    for code in settings.valid_sources:
        subj = db.execute(select(Subject).where(Subject.code == code)).scalar_one_or_none()
        if subj is None:
            subj = Subject(
                code=code,
                name=SUBJECT_NAMES.get(code, code),
                description=f"{SUBJECT_NAMES.get(code, code)}方向学习资料",
            )
            db.add(subj)
            db.flush()
        result[code] = subj.id
    db.commit()
    return result


def _embed_many(client, texts: list[str]) -> list[list[float]]:
    """批量嵌入；请求过大/限流时自动递归减半，保证健壮性。"""
    results: list[list[float] | None] = [None] * len(texts)

    def run(batch: list[str]) -> list[list[float]]:
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                return client.embed_texts(batch)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"嵌入请求失败: {last_err}") from last_err

    stack = [list(range(len(texts)))]
    while stack:
        ids = stack.pop()
        batch = [texts[i] for i in ids]
        try:
            vectors = run(batch)
        except Exception:
            if len(ids) <= 1:
                raise
            mid = len(ids) // 2
            stack.append(ids[mid:])
            stack.append(ids[:mid])
        else:
            if len(vectors) != len(ids):
                raise RuntimeError(
                    f"嵌入返回数量 {len(vectors)} != 请求数 {len(ids)}"
                )
            for idx, vec in zip(ids, vectors):
                results[idx] = vec

    # 类型收窄
    return [v for v in results if v is not None]  # type: ignore[misc]


def ingest_document(
    store: MilvusStore,
    db,
    client,
    doc: RawDocument,
    subject_code: str,
    subject_id: int,
    *,
    dry_run: bool = False,
) -> dict:
    """解析单文档并入库，返回统计。"""
    parents = chunk_pages(doc.pages)
    child_count = sum(len(p.children) for p in parents)
    print(
        f"  {doc.title} ({doc.file_type}) 页数={len(doc.pages)} "
        f"父块={len(parents)} 子块={child_count}"
    )

    if dry_run:
        return {"title": doc.title, "parents": len(parents), "children": child_count}

    # 先落 documents 记录（pending），失败可标记
    record = Document(
        subject_id=subject_id,
        title=doc.title,
        file_path=str(doc.path),
        file_type=doc.file_type,
        chunk_count=0,
        status=DocumentStatus.pending,
    )
    db.add(record)
    db.flush()
    doc_id = record.id

    # 收集所有子块文本
    text_rows: list[tuple[str, str, int, str]] = []  # (child_id, text, page, parent_id)
    for parent in parents:
        for child in parent.children:
            text_rows.append(
                (parent.parent_chunk_id, child, parent.page, parent.parent_chunk_id)
            )

    # 嵌入（分批）
    vectors: list[list[float]] = []
    for i in range(0, len(text_rows), EMBED_BATCH):
        batch = [t for _, t, _, _ in text_rows[i : i + EMBED_BATCH]]
        vectors.extend(_embed_many(client, batch))
        print(f"    已嵌入 {min(i + EMBED_BATCH, len(text_rows))}/{len(text_rows)} 子块")
        if EMBEDDING_DIM and vectors and len(vectors[-1]) != EMBEDDING_DIM:
            raise RuntimeError(
                f"嵌入维度 {len(vectors[-1])} != 期望 {EMBEDDING_DIM}，请核对 collection 与模型"
            )

    # 组装 Milvus 行并写入（父文本冗余存于每行 parent_text）
    rows = [
        {
            "chunk_id": text_rows[i][0] + f"_{i}",
            "parent_chunk_id": text_rows[i][0],
            "document_id": doc_id,
            "doc_title": doc.title,
            "subject_code": subject_code,
            "chunk_text": text_rows[i][1],
            "parent_text": _parent_of(text_rows[i][0], parents),
            "page": text_rows[i][2],
            "embedding": vectors[i],
        }
        for i in range(len(text_rows))
    ]
    store.ensure_collection()
    for i in range(0, len(rows), 64):
        store.insert(rows[i : i + 64])
    try:
        store.flush()  # 让 dense/sparse(BM25) 索引立即可检索
    except Exception:
        pass

    record.chunk_count = len(rows)
    record.status = DocumentStatus.processed
    db.commit()
    return {
        "title": doc.title,
        "document_id": doc_id,
        "parents": len(parents),
        "children": len(rows),
    }


def _parent_of(parent_id: str, parents) -> str:
    for p in parents:
        if p.parent_chunk_id == parent_id:
            return p.text
    return ""


def ingest_dir(
    directory: str | Path,
    subject_code: str,
    *,
    reset: bool = False,
    dry_run: bool = False,
) -> list[dict]:
    docs = load_dir(directory)
    if not docs:
        raise FileNotFoundError(f"{directory} 下没有可解析的 pdf/docx")

    if dry_run:
        print(f"dry-run 解析分块 {len(docs)} 个文档（学科过滤不生效）")
        summary = []
        for doc in docs:
            result = ingest_document(
                None, None, None, doc, subject_code, 0, dry_run=True
            )
            summary.append(result)
        total = sum(r.get("children", 0) for r in summary)
        print(f"\n=== dry-run 完成: {len(summary)} 个文档, 子块合计 {total} ===")
        return summary

    store = get_store()
    client = get_llm_client()
    db = SessionLocal()

    summary: list[dict] = []
    try:
        subj_ids = seed_subjects(db)
        if subject_code not in subj_ids:
            raise ValueError(
                f"subject '{subject_code}' 不在 valid_sources "
                f"{settings.valid_sources} 中"
            )
        subject_id = subj_ids[subject_code]

        if reset:
            if store.has_collection():
                store.drop_collection()
                print("已 drop 旧 collection（schema 重建）")
            db.execute(delete(Document).where(Document.subject_id == subject_id))
            db.commit()

        print(f"待入库 {len(docs)} 个文档，学科='{subject_code}'")

        for doc in docs:
            result = ingest_document(
                store, db, client, doc, subject_code, subject_id
            )
            summary.append(result)
    finally:
        db.close()

    total_children = sum(r.get("children", 0) for r in summary)
    print(f"\n=== 完成: {len(summary)} 个文档, 子块合计 {total_children} ===")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="ai_data 语料入库到 Milvus + MySQL")
    parser.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parents[2] / "documents/data/ai_data"),
        help="语料目录，默认 documents/data/ai_data",
    )
    parser.add_argument("--subject", default="ai", help="归属学科 code，默认 ai")
    parser.add_argument("--reset", action="store_true", help="重建 collection 并清空该学科 documents 记录")
    parser.add_argument("--dry-run", action="store_true", help="只解析分块打印统计，不调用嵌入/不写库")
    args = parser.parse_args()

    if not args.dry_run:
        init_db()  # 确保表存在（幂等）

    ingest_dir(args.dir, args.subject, reset=args.reset, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
