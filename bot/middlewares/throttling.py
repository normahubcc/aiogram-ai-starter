"""Rate limiting / throttling middleware for Aiogram 3."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware enforcing per-user rate limiting to prevent spam and flood."""

    def __init__(self, rate_limit: float = 1.0):
        super().__init__()
        self.rate_limit = rate_limit
        self._user_timestamps: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id is not None:
            now = time.monotonic()
            last_time = self._user_timestamps.get(user_id, 0.0)

            # Check if cooldown is active
            if (now - last_time) < self.rate_limit:
                if isinstance(event, CallbackQuery):
                    await event.answer("⏳ Слишком часто! Пожалуйста, подождите секунду.", show_alert=True)
                elif isinstance(event, Message):
                    # Suppress or optionally warn user
                    pass
                return None

            # Clean cache if it grows too large
            if len(self._user_timestamps) > 10000:
                cutoff = now - (self.rate_limit * 10)
                self._user_timestamps = {
                    uid: ts for uid, ts in self._user_timestamps.items() if ts > cutoff
                }

            self._user_timestamps[user_id] = now

        return await handler(event, data)
