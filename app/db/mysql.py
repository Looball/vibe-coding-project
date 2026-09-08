"""MySQL 数据库客户端：基于 SQLAlchemy 2.0 + PyMySQL，配置来自 config.ini 的 [mysql] 节。"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.mysql_url,
    pool_pre_ping=True,          # 取连接前探测，避免拿到失效连接
    pool_recycle=3600,           # 连接 1 小时回收，规避 MySQL 8h 超时
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：请求级数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """创建尚未存在的表（需先导入模型模块完成注册）。"""
    from app.models import mysql_models  # noqa: F401  注册表到 Base.metadata

    Base.metadata.create_all(bind=engine)


def ping() -> bool:
    """连通性检查：SELECT 1。"""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
