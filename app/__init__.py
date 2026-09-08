import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.core.config import settings

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"
# 默认前后端分离：后端只提供 API。如需后端代托管前端，设 VIBEQA_SERVE_FRONTEND=1
SERVE_FRONTEND = os.environ.get("VIBEQA_SERVE_FRONTEND", "").lower() in ("1", "true", "yes")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="黑马程序员智能问答系统",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # 前后端分离后允许跨域
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    # 仅当显式开启时由后端托管前端静态资源（单命令演示用）
    if SERVE_FRONTEND and (FRONTEND_DIR / "static").is_dir():
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")

        @app.get("/", include_in_schema=False)
        async def index() -> FileResponse:
            return FileResponse(FRONTEND_DIR / "index.html")

    return app
