"""API 集成测试：需要本地服务(MySQL/Redis/Milvus)在线。

默认被 addopts `-m not integration` 跳过；手动运行：
    uv run python -m pytest -m integration
"""
import pytest
from fastapi.testclient import TestClient

from app import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app())


def test_health_all_up(client: TestClient):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["services"]["mysql"] == "up"


def test_subjects_listed(client: TestClient):
    resp = client.get("/api/v1/subjects")
    assert resp.status_code == 200
    codes = {s["code"] for s in resp.json()}
    assert "ai" in codes
    assert len(codes) >= 5


def test_conversation_lifecycle(client: TestClient):
    # 创建
    created = client.post("/api/v1/conversations", json={"title": "集成测试"})
    assert created.status_code == 201
    cid = created.json()["id"]

    # 发送问候消息（走 greeting 路径，不触发在线 LLM）
    sent = client.post(f"/api/v1/conversations/{cid}/messages", json={"query": "你好"})
    assert sent.status_code == 200
    body = sent.json()
    assert body["greeting"] is True

    # 历史：倒序返回 user+assistant 两条
    history = client.get(f"/api/v1/conversations/{cid}/messages").json()
    assert len(history["messages"]) == 2
    assert history["messages"][0]["role"] == "assistant"  # 最新在前

    # 列表含该会话且消息数=2
    listed = client.get("/api/v1/conversations").json()
    conv = next(c for c in listed if c["id"] == cid)
    assert conv["message_count"] == 2

    # 清除
    assert client.delete(f"/api/v1/conversations/{cid}").status_code == 204
    after = client.get("/api/v1/conversations").json()
    assert all(c["id"] != cid for c in after)
