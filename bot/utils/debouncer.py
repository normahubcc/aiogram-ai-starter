"""Telegram Stream Debouncer for smooth LLM token streaming.

Buffers rapid token streams, edits messages at controlled intervals (~800ms)
to prevent Telegram FloodWait rate limits, gracefully recovers from Markdown
formatting errors, and guarantees a final flush.
"""

import asyncio
import logging
import time

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter

logger = logging.getLogger(__name__)


class TelegramStreamDebouncer:
    """Debounces streaming token updates when updating a Telegram message."""

    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        interval: float = 0.8,
        parse_mode: str | None = ParseMode.MARKDOWN,
        max_length: int = 4000,
    ):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.interval = interval
        self.parse_mode = parse_mode
        self.max_length = max_length

        self.full_text: str = ""
        self.last_sent_text: str = ""
        self.last_edit_time: float = 0.0
        self._lock = asyncio.Lock()
        self._cooldown_until: float = 0.0

    @property
    def current_text(self) -> str:
        """Return the accumulated text so far."""
        return self.full_text

    async def add_token(self, token: str) -> None:
        """Add a token to the buffer and edit the message if interval elapsed."""
        if not token:
            return

        self.full_text += token
        now = time.monotonic()

        # If we are under rate-limit cooldown or interval has not elapsed yet, defer
        if now < self._cooldown_until:
            return

        if (now - self.last_edit_time) >= self.interval:
            await self._edit_message(self.full_text)

    async def flush(self) -> str:
        """Force a final edit with all accumulated content and return the final text."""
        async with self._lock:
            if self.full_text and self.full_text != self.last_sent_text:
                await self._edit_message_unlocked(self.full_text, is_final=True)
            return self.full_text

    async def _edit_message(self, text: str, is_final: bool = False) -> None:
        """Safely edit the message under lock."""
        async with self._lock:
            await self._edit_message_unlocked(text, is_final=is_final)

    async def _edit_message_unlocked(self, text: str, is_final: bool = False) -> None:
        """Edit the message with error handling and fallback mechanisms."""
        # Trim if text exceeds single Telegram message length limit
        display_text = text[: self.max_length] if len(text) > self.max_length else text
        if not display_text.strip():
            return

        # Avoid redundant edits
        if display_text == self.last_sent_text and not is_final:
            return

        now = time.monotonic()
        if now < self._cooldown_until:
            return

        # First attempt: edit using configured parse mode (Markdown)
        try:
            await self.bot.edit_message_text(
                text=display_text,
                chat_id=self.chat_id,
                message_id=self.message_id,
                parse_mode=self.parse_mode,
            )
            self.last_sent_text = display_text
            self.last_edit_time = time.monotonic()
            return
        except TelegramRetryAfter as e:
            # Caught FloodWait / RetryAfter: back off
            logger.warning(
                "Telegram FloodWait encountered for chat %d, backing off for %d seconds",
                self.chat_id,
                e.retry_after,
            )
            self._cooldown_until = time.monotonic() + e.retry_after
            if is_final:
                await asyncio.sleep(e.retry_after)
                # Retry once for final flush
                try:
                    await self.bot.edit_message_text(
                        text=display_text,
                        chat_id=self.chat_id,
                        message_id=self.message_id,
                        parse_mode=self.parse_mode,
                    )
                    self.last_sent_text = display_text
                except Exception:
                    pass
            return
        except TelegramBadRequest as e:
            err_msg = str(e).lower()
            # Message is identical to existing text
            if "message is not modified" in err_msg:
                self.last_sent_text = display_text
                return

            # Markdown parsing syntax error due to partial tokens (e.g. unclosed * or `)
            if "can't parse entities" in err_msg or "entity" in err_msg or "parse" in err_msg:
                logger.debug(
                    "Markdown parsing error during streaming, falling back to plain text: %s",
                    e,
                )
                try:
                    # Graceful fallback: render without formatting
                    await self.bot.edit_message_text(
                        text=display_text,
                        chat_id=self.chat_id,
                        message_id=self.message_id,
                        parse_mode=None,
                    )
                    self.last_sent_text = display_text
                    self.last_edit_time = time.monotonic()
                    return
                except Exception as fallback_err:
                    logger.debug("Plain text fallback failed: %s", fallback_err)
            else:
                logger.warning("TelegramBadRequest while updating message: %s", e)
        except Exception as exc:
            logger.debug("Unexpected error during stream edit: %s", exc)

        self.last_edit_time = time.monotonic()
