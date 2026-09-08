"""Milvus 向量数据库客户端：配置来自 config.ini 的 [milvus] 节。

collection（默认 RAGQA）为混合检索（Hybrid）schema：
    稠密路 embedding(FLOAT_VECTOR, dim=1024, IVF_FLAT/COSINE)
        向量来自 .env 指定模型（BAAI/bge-m3，SiliconFlow 在线嵌入）
    稀疏路 chunk_text 经服务端 BM25 FUNCTION（analyzer=jieba 分词）产出
        sparse(SPARSE_FLOAT_VECTOR / SPARSE_INVERTED_INDEX / BM25)
    两路召回后用 RRF 融合（hybrid_search）。

业务字段：chunk_id / parent_chunk_id / document_id / doc_title /
subject_code / chunk_text / parent_text / page

Parent-Child 检索：子块入库（chunk_text + embedding），命中后回取
父块（parent_text）作 LLM 上下文。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymilvus import (
    AnnSearchRequest,
    DataType,
    Function,
    FunctionType,
    MilvusClient,
    RRFRanker,
)

from app.core.config import settings

EMBEDDING_DIM = 1024  # BAAI/bge-m3 dense 输出维度

_store: "MilvusStore | None" = None


@dataclass
class SearchHit:
    chunk_id: str
    parent_chunk_id: str
    document_id: int
    doc_title: str
    subject_code: str
    chunk_text: str
    parent_text: str
    page: int
    score: float


class MilvusStore:
    """Milvus 客户端封装：连接管理、建集、写入、检索、删除。"""

    _OUTPUT_FIELDS = [
        "chunk_id",
        "parent_chunk_id",
        "document_id",
        "doc_title",
        "subject_code",
        "chunk_text",
        "parent_text",
        "page",
    ]

    def __init__(self, host: str, port: int, database: str, collection: str) -> None:
        self._uri = f"http://{host}:{port}"
        self._database = database
        self._collection = collection
        self._client: MilvusClient | None = None

    # ---------- 连接管理 ----------

    @property
    def client(self) -> MilvusClient:
        if self._client is None:
            self._client = MilvusClient(uri=self._uri)
            self._ensure_database()
        return self._client

    def _ensure_database(self) -> None:
        if self._database not in self._client.list_databases():
            self._client.create_database(self._database)
        switch_db = getattr(self._client, "use_database", None) or self._client.using_database
        switch_db(self._database)

    def has_collection(self) -> bool:
        return self.client.has_collection(self._collection)

    # ---------- 建集 ----------

    def drop_collection(self) -> None:
        """删除 collection（重建 Schema 时使用）。"""
        self.client.drop_collection(self._collection)

    def ensure_collection(self) -> None:
        """若 collection 不存在则创建混合检索 Schema（BM25/jieba sparse + dense）。"""
        if self.has_collection():
            return

        schema = MilvusClient.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=64)
        schema.add_field("parent_chunk_id", DataType.VARCHAR, max_length=64)
        schema.add_field("document_id", DataType.INT64)
        schema.add_field("doc_title", DataType.VARCHAR, max_length=200)
        schema.add_field("subject_code", DataType.VARCHAR, max_length=20)
        schema.add_field(
            "chunk_text",
            DataType.VARCHAR,
            max_length=2000,
            enable_analyzer=True,
            analyzer_params={"tokenizer": "jieba"},
        )
        schema.add_field("parent_text", DataType.VARCHAR, max_length=20000)
        schema.add_field("page", DataType.INT64)
        schema.add_field("embedding", DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM)
        # 稀疏路：BM25 FUNCTION 依据 chunk_text(服务端 jieba 分词) 产出 sparse
        schema.add_field("sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_function(
            Function(
                name="bm25",
                function_type=FunctionType.BM25,
                input_field_names=["chunk_text"],
                output_field_names="sparse",
            )
        )

        index_params = MilvusClient.prepare_index_params()
        index_params.add_index(
            field_name="embedding",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 1024},
        )
        index_params.add_index(
            field_name="sparse",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="BM25",
        )

        self.client.create_collection(
            collection_name=self._collection,
            schema=schema,
            index_params=index_params,
        )

    # ---------- 写入 ----------

    def insert(self, rows: list[dict[str, Any]]) -> list[int]:
        """写入向量数据（sparse 由服务端 BM25 FUNCTION 依据 chunk_text 自动产出）。"""
        result = self.client.insert(collection_name=self._collection, data=rows)
        return result.get("ids", [])

    def flush(self) -> None:
        """强制落盘，使计数/检索立即可见。"""
        self.client.flush(self._collection)

    # ---------- 检索 ----------

    def search(
        self,
        query_vector: list[float],
        subject_code: str | None = None,
        limit: int | None = None,
        nprobe: int = 16,
    ) -> list[SearchHit]:
        """纯稠密向量检索（回退路径）。"""
        expr = f'subject_code == "{subject_code}"' if subject_code else None
        result = self.client.search(
            collection_name=self._collection,
            data=[query_vector],
            filter=expr,
            limit=limit or settings.retrieval_k,
            output_fields=self._OUTPUT_FIELDS,
            search_params={"metric_type": "COSINE", "params": {"nprobe": nprobe}},
        )
        return self._parse_search(result)

    def hybrid_search(
        self,
        query_text: str,
        query_vector: list[float],
        subject_code: str | None = None,
        limit: int | None = None,
        nprobe: int = 16,
    ) -> list[SearchHit]:
        """混合检索：稠密(bge-m3/COSINE) + 稀疏(服务端 BM25+jieba) 双路召回后 RRF 融合。

        Args:
            query_text: 原文/改写后查询，服务端 BM25 据此分词检索 sparse。
            query_vector: 查询的 bge-m3 稠密向量。
            subject_code: 学科过滤，None 表示全学科。
            limit: 融合后返回条数，默认 retrieval_k。
        """
        expr = f'subject_code == "{subject_code}"' if subject_code else None
        k = settings.retrieval_k
        dense_req = AnnSearchRequest(
            data=[query_vector],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": nprobe}},
            limit=k,
            expr=expr,
        )
        sparse_req = AnnSearchRequest(
            data=[query_text],  # BM25 FUNCTION：传文本由服务端分词
            anns_field="sparse",
            param={},
            limit=k,
            expr=expr,
        )
        result = self.client.hybrid_search(
            collection_name=self._collection,
            reqs=[dense_req, sparse_req],
            ranker=RRFRanker(),
            limit=limit or k,
            output_fields=self._OUTPUT_FIELDS,
        )
        return self._parse_search(result)

    def _parse_search(self, result) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for hit in result[0]:
            entity = hit.get("entity", {})
            hits.append(
                SearchHit(
                    chunk_id=entity.get("chunk_id", ""),
                    parent_chunk_id=entity.get("parent_chunk_id", ""),
                    document_id=entity.get("document_id", 0),
                    doc_title=entity.get("doc_title", ""),
                    subject_code=entity.get("subject_code", ""),
                    chunk_text=entity.get("chunk_text", ""),
                    parent_text=entity.get("parent_text", ""),
                    page=entity.get("page", 0),
                    score=hit.get("distance", 0.0),
                )
            )
        return hits

    # ---------- 删除 ----------

    def delete_by_filter(self, expr: str) -> int:
        """按过滤条件删除，例如 'document_id == 1'。"""
        result = self.client.delete(collection_name=self._collection, filter=expr)
        return len(result.get("ids", []))


def get_store() -> MilvusStore:
    """获取全局 MilvusStore（延迟连接，进程内单例）。"""
    global _store
    if _store is None:
        _store = MilvusStore(
            host=settings.milvus_host,
            port=settings.milvus_port,
            database=settings.milvus_database,
            collection=settings.milvus_collection,
        )
    return _store


def ping() -> bool:
    """连通性检查：确认目标 collection 存在。"""
    return get_store().has_collection()
