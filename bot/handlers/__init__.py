"""Handlers package aggregating all bot routers."""

from aiogram import Router

from bot.handlers.admin import router as admin_router
from bot.handlers.chat import router as chat_router
from bot.handlers.common import router as common_router
from bot.handlers.model import router as model_router
from bot.handlers.referral import router as referral_router
from bot.handlers.stars import router as stars_router
from bot.handlers.video import router as video_router
from bot.handlers.voice import router as voice_router


def setup_routers() -> Router:
    """Combine all feature routers into a single root router."""
    root_router = Router(name="root_router")
    root_router.include_router(common_router)
    root_router.include_router(admin_router)
    root_router.include_router(stars_router)
    root_router.include_router(referral_router)
    root_router.include_router(model_router)
    root_router.include_router(video_router)
    root_router.include_router(voice_router)
    root_router.include_router(chat_router)  # Chat handler is registered last to catch remaining text
    return root_router


__all__ = [
    "admin_router",
    "chat_router",
    "common_router",
    "model_router",
    "referral_router",
    "setup_routers",
    "stars_router",
    "video_router",
    "voice_router",
]

