"""Tests for TelegramStreamDebouncer."""

from unittest.mock import AsyncMock

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.methods import EditMessageText

from bot.utils.debouncer import TelegramStreamDebouncer


@pytest.mark.asyncio
async def test_debouncer_buffers_and_flushes():
    """Test that tokens are buffered and final flush sends full text."""
    mock_bot = AsyncMock()
    debouncer = TelegramStreamDebouncer(
        bot=mock_bot,
        chat_id=123,
        message_id=456,
        interval=0.8,
    )

    await debouncer.add_token("Hello ")
    await debouncer.add_token("world")
    await debouncer.add_token("!")

    assert debouncer.current_text == "Hello world!"

    final_text = await debouncer.flush()
    assert final_text == "Hello world!"

    mock_bot.edit_message_text.assert_called_with(
        text="Hello world!",
        chat_id=123,
        message_id=456,
        parse_mode="Markdown",
    )


@pytest.mark.asyncio
async def test_debouncer_interval_throttling():
    """Test that rapid successive add_token calls do not trigger edits before interval."""
    mock_bot = AsyncMock()
    debouncer = TelegramStreamDebouncer(
        bot=mock_bot,
        chat_id=123,
        message_id=456,
        interval=1.0,
    )

    # First edit will trigger because last_edit_time is 0
    await debouncer.add_token("First token ")
    assert mock_bot.edit_message_text.call_count == 1

    # Immediate second and third tokens within 1.0s window should NOT trigger edits
    await debouncer.add_token("Second ")
    await debouncer.add_token("Third")
    assert mock_bot.edit_message_text.call_count == 1

    # Flush should perform the second edit with full text
    await debouncer.flush()
    assert mock_bot.edit_message_text.call_count == 2
    assert debouncer.current_text == "First token Second Third"


@pytest.mark.asyncio
async def test_debouncer_markdown_parse_fallback():
    """Test graceful fallback to plain text when Telegram rejects malformed Markdown."""
    mock_bot = AsyncMock()
    dummy_method = EditMessageText(chat_id=123, message_id=456, text="dummy")
    # First call fails with Markdown error, fallback succeeds
    mock_bot.edit_message_text.side_effect = [
        TelegramBadRequest(method=dummy_method, message="Bad Request: can't parse entities in message text"),
        AsyncMock(),
    ]

    debouncer = TelegramStreamDebouncer(
        bot=mock_bot,
        chat_id=123,
        message_id=456,
        interval=0.1,
    )

    await debouncer.add_token("Unclosed **markdown token")
    await debouncer.flush()

    assert mock_bot.edit_message_text.call_count == 2
    # Second call must be fallback with parse_mode=None
    second_call_kwargs = mock_bot.edit_message_text.call_args_list[1].kwargs
    assert second_call_kwargs["parse_mode"] is None


@pytest.mark.asyncio
async def test_debouncer_handles_message_not_modified():
    """Test that 'message is not modified' error is silently ignored."""
    dummy_method = EditMessageText(chat_id=123, message_id=456, text="dummy")
    mock_bot = AsyncMock()
    mock_bot.edit_message_text.side_effect = TelegramBadRequest(
        method=dummy_method,
        message="Bad Request: message is not modified: specified new message content and reply markup are exactly the same",
    )

    debouncer = TelegramStreamDebouncer(
        bot=mock_bot,
        chat_id=123,
        message_id=456,
    )

    await debouncer.add_token("Identical text")
    await debouncer.flush()
    # Should not raise exception
    assert debouncer.current_text == "Identical text"


@pytest.mark.asyncio
async def test_debouncer_handles_flood_wait():
    """Test that TelegramRetryAfter / FloodWait applies cooldown."""
    dummy_method = EditMessageText(chat_id=123, message_id=456, text="dummy")
    mock_bot = AsyncMock()
    mock_bot.edit_message_text.side_effect = [
        TelegramRetryAfter(method=dummy_method, retry_after=1, message="Flood control exceeded"),
        AsyncMock(),
    ]

    debouncer = TelegramStreamDebouncer(
        bot=mock_bot,
        chat_id=123,
        message_id=456,
        interval=0.1,
    )

    await debouncer.add_token("Token during flood")
    # Immediate next token should be deferred by cooldown
    await debouncer.add_token(" Another token")

    assert debouncer.current_text == "Token during flood Another token"
