"""Redis 客户端：配置来自 config.ini 的 [redis] 节，使用连接池复用。"""
from __future__ import annotations

import json
from typing import Any

import redis

from app.core.config import settings

_pool: redis.ConnectionPool | None = None


def get_client() -> redis.Redis:
    """获取全局 Redis 连接（延迟初始化，进程内单例）。"""
    global _pool
    if _pool is None:
        _pool = redis.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            db=settings.redis_db,
            decode_responses=True,  # 返回 str 而非 bytes
        )
    return redis.Redis(connection_pool=_pool)


def set_json(key: str, value: Any, ex: int | None = None) -> bool:
    """写入 JSON 缓存，ex 单位为秒。"""
    return bool(get_client().set(key, json.dumps(value, ensure_ascii=False), ex=ex))


def get_json(key: str) -> Any | None:
    """读取 JSON 缓存，不存在或解析失败返回 None。"""
    raw = get_client().get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def delete(key: str) -> int:
    return get_client().delete(key)


def ping() -> bool:
    """连通性检查。"""
    return bool(get_client().ping())
