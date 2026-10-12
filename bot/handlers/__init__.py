"""Handlers package aggregating all bot routers."""

from aiogram import Router

from bot.handlers.chat import router as chat_router
from bot.handlers.common import router as common_router
from bot.handlers.model import router as model_router
from bot.handlers.video import router as video_router
from bot.handlers.voice import router as voice_router


def setup_routers() -> Router:
    """Combine all feature routers into a single root router."""
    root_router = Router(name="root_router")
    root_router.include_router(common_router)
    root_router.include_router(model_router)
    root_router.include_router(video_router)
    root_router.include_router(voice_router)
    root_router.include_router(chat_router)  # Chat handler is registered last to catch remaining text
    return root_router


__all__ = [
    "chat_router",
    "common_router",
    "model_router",
    "setup_routers",
    "video_router",
    "voice_router",
]
