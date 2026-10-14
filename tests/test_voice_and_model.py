"""Unit tests for model selector and voice/video_note transcription handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import CallbackQuery, Chat, Message, User, Voice

from bot.handlers.model import callback_select_model, handle_model_command
from bot.handlers.voice import handle_voice_message
from bot.keyboards.inline import get_models_keyboard
from bot.utils.context import ConversationManager


def test_get_models_keyboard():
    """Verify models keyboard marks active model with checkmark."""
    current_model = "deepseek-v4.1-flash"
    kb = get_models_keyboard(current_model)
    buttons = [row[0] for row in kb.inline_keyboard]

    # Verify active button has checkmark
    active_btn = next(b for b in buttons if b.callback_data == f"select_model:{current_model}")
    assert "✅" in active_btn.text

    # Verify inactive button has white circle
    inactive_btn = next(b for b in buttons if b.callback_data == "select_model:claude-sonnet-5-5")
    assert "⚪" in inactive_btn.text


@pytest.mark.asyncio
async def test_handle_model_command():
    """Verify /model command answers with current model and keyboard."""
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(spec=User, id=42)
    msg.answer = AsyncMock()

    cm = ConversationManager()
    cm.set_model(42, "claude-sonnet-5-5")

    await handle_model_command(msg, cm)
    msg.answer.assert_called_once()
    assert "claude-sonnet-5-5" in msg.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_callback_select_model():
    """Verify clicking model button updates user preference in conversation manager."""
    cb = MagicMock(spec=CallbackQuery)
    cb.data = "select_model:claude-sonnet-5-5"
    cb.from_user = MagicMock(spec=User, id=99)
    cb.answer = AsyncMock()
    cb.message = MagicMock(spec=Message)
    cb.message.edit_text = AsyncMock()

    cm = ConversationManager()
    await callback_select_model(cb, cm)

    assert cm.get_model(99) == "claude-sonnet-5-5"
    cb.answer.assert_called_once()
    assert "Claude Sonnet" in cb.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_handle_voice_and_video_note_handlers():
    """Verify handle_voice_message processes voice and video_note correctly."""
    bot = MagicMock()
    bot.send_chat_action = AsyncMock()
    file_info = MagicMock(file_path="voice/file_1.oga")
    bot.get_file = AsyncMock(return_value=file_info)
    bot.download_file = AsyncMock()

    config = MagicMock()
    config.stream_debounce_interval = 0.5

    client = MagicMock()
    client.transcribe_audio = AsyncMock(return_value="Привет, как дела?")

    async def dummy_stream(*args, **kwargs):
        yield "Отлично, "
        yield "готов помочь!"

    client.stream_chat_completion = dummy_stream

    cm = ConversationManager()

    # 1. Test voice note
    voice_msg = MagicMock(spec=Message)
    voice_msg.voice = MagicMock(spec=Voice, file_id="voice_id_123")
    voice_msg.video_note = None
    voice_msg.from_user = MagicMock(spec=User, id=77)
    voice_msg.chat = MagicMock(spec=Chat, id=77)
    status_msg = MagicMock(spec=Message)
    status_msg.edit_text = AsyncMock()
    answer_msg = MagicMock(spec=Message, message_id=555)
    voice_msg.answer = AsyncMock(side_effect=[status_msg, answer_msg])

    await handle_voice_message(voice_msg, bot, config, client, cm)

    client.transcribe_audio.assert_called_once()
    assert cm.get_messages(77)[-2]["content"] == "Привет, как дела?"
