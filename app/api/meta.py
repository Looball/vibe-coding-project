"""元信息接口：学科列表 + 健康检查。"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import HealthOut, SubjectOut
from app.db.mysql import get_db
from app.models.mysql_models import Subject

router = APIRouter(tags=["meta"])


@router.get("/subjects", response_model=list[SubjectOut], summary="学科列表")
def list_subjects(db: Session = Depends(get_db)) -> list[Subject]:
    return db.execute(select(Subject).order_by(Subject.id)).scalars().all()


@router.get("/health", response_model=HealthOut, summary="健康检查")
def health_check() -> HealthOut:
    from app.db import milvus, mysql, redis

    services: dict[str, str] = {}
    for name, probe in [
        ("mysql", mysql.ping),
        ("redis", redis.ping),
        ("milvus", milvus.ping),
    ]:
        try:
            services[name] = "up" if probe() else "down"
        except Exception:
            services[name] = "down"

    overall = "ok" if all(v == "up" for v in services.values()) else "degraded"
    return HealthOut(status=overall, services=services)
