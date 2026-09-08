"""配置中心：解析 config.ini 配置文件，敏感信息(API Key)通过环境变量注入。

config.ini 默认查找位置(按优先级):
    1. 环境变量 EDURAG_CONFIG 指定的路径
    2. 项目根目录 config.ini
    3. documents/data/config.ini
"""
from __future__ import annotations

import configparser
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(os.environ.get("EDURAG_CONFIG", PROJECT_ROOT / "documents" / "data" / "config.ini"))
if CONFIG_PATH.is_file():
    load_dotenv(PROJECT_ROOT / ".env")

_parser = configparser.ConfigParser()
if not CONFIG_PATH.is_file():
    raise FileNotFoundError(f"未找到配置文件 {CONFIG_PATH}，可通过环境变量 EDURAG_CONFIG 指定路径")


@dataclass
class Settings:
    """类型化配置对象，字段来源于 config.ini 各节。"""

    # ---- [mysql] ----
    mysql_host: str
    mysql_user: str
    mysql_password: str
    mysql_database: str
    # ---- [redis] ----
    redis_host: str
    redis_port: int
    redis_password: str
    redis_db: int
    # ---- [milvus] ----
    milvus_host: str
    milvus_port: int
    milvus_database: str
    milvus_collection: str
    # ---- [llm] 阿里云 DashScope ----
    llm_model: str
    dashscope_base_url: str
    embedding_model: str = "text-embedding-v3"
    # ---- [retrieval] ----
    parent_chunk_size: int = 1200
    child_chunk_size: int = 300
    chunk_overlap: int = 50
    retrieval_k: int = 10
    candidate_m: int = 3
    # ---- [app] ----
    app_name: str = "EduRAG"
    valid_sources: list[str] = field(default_factory=list)
    customer_service_phone: str = ""
    # ---- [logger] ----
    log_file: str = "/logs/app.log"

    @property
    def dashscope_api_key(self) -> str:
        key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
        if not key:
            raise RuntimeError("缺少 DASHSCOPE_API_KEY，请写入 .env 文件或设置环境变量")
        return key

    @property
    def mysql_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:3306/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def milvus_uri(self) -> str:
        return f"http://{self.milvus_host}:{self.milvus_port}"


def load_settings(path: str | Path | None = None) -> Settings:
    cfg_path = Path(path) if path else CONFIG_PATH
    parser = configparser.ConfigParser()
    parser.read(cfg_path, encoding="utf-8")

    mysql, redis = parser["mysql"], parser["redis"]
    milvus, llm = parser["milvus"], parser["llm"]
    retrieval, app, logger = parser["retrieval"], parser["app"], parser["logger"]

    return Settings(
        # MySQL
        mysql_host=mysql["host"],
        mysql_user=mysql["user"],
        mysql_password=mysql["password"],
        mysql_database=mysql["database"],
        # Redis
        redis_host=redis["host"],
        redis_port=int(redis["port"]),
        redis_password=redis["password"],
        redis_db=int(redis["db"]),
        # Milvus
        milvus_host=milvus["host"],
        milvus_port=int(milvus["port"]),
        milvus_database=milvus["database_name"],
        milvus_collection=milvus["collection_name"],
        # LLM
        llm_model=llm["model"],
        dashscope_base_url=llm["dashscope_base_url"],
        # 检索
        parent_chunk_size=int(retrieval["parent_chunk_size"]),
        child_chunk_size=int(retrieval["child_chunk_size"]),
        chunk_overlap=int(retrieval["chunk_overlap"]),
        retrieval_k=int(retrieval["retrieval_k"]),
        candidate_m=int(retrieval["candidate_m"]),
        # 应用
        valid_sources=json.loads(app["valid_sources"]),
        customer_service_phone=str(app["customer_service_phone"]),
        # 日志
        log_file=logger["log_file"],
    )


settings = load_settings()


SUBJECT_LABELS = {
    "ai": "人工智能",
    "java": "Java",
    "test": "软件测试",
    "ops": "运维",
    "bigdata": "大数据",
}


def subject_label(subject_code: str | None) -> str:
    if not subject_code:
        return "通用"
    return SUBJECT_LABELS.get(subject_code, subject_code)
