"""API 路由聚合。"""
from fastapi import APIRouter

from app.api import chat, conversations, meta

api_router = APIRouter()
api_router.include_router(meta.router)
api_router.include_router(chat.router)
api_router.include_router(conversations.router)
