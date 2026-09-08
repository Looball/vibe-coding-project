"""配置解析测试（读取 config.ini，离线）。"""
from app.core.config import settings


def test_mysql_config_parsed():
    assert settings.mysql_host == "localhost"
    assert settings.mysql_user
    assert settings.mysql_password
    assert settings.mysql_database


def test_milvus_config_parsed():
    assert settings.milvus_host == "localhost"
    assert settings.milvus_port == 19530
    assert settings.milvus_database
    assert settings.milvus_collection


def test_retrieval_params_int():
    assert settings.parent_chunk_size > 0
    assert settings.child_chunk_size > 0
    assert settings.parent_chunk_size > settings.child_chunk_size
    assert settings.retrieval_k > 0
    assert settings.candidate_m > 0


def test_valid_sources_contains_ai():
    assert "ai" in settings.valid_sources
    assert settings.valid_sources


def test_llm_config():
    assert settings.dashscope_base_url.startswith("https://")
    assert settings.llm_model
    assert settings.embedding_model.startswith("text-embedding")


def test_connection_urls_built():
    assert settings.mysql_url.startswith("mysql+pymysql://")
    assert "3306" in settings.mysql_url
    assert settings.milvus_uri.endswith(":19530")
