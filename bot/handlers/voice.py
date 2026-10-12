"""Voice message handler: downloads audio, transcribes via Whisper, and streams response."""

import io
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.types import Message

from bot.client.normahub import NormaHubClient, NormaHubError
from bot.config import BotConfig
from bot.utils.context import ConversationManager
from bot.utils.debouncer import TelegramStreamDebouncer

logger = logging.getLogger(__name__)
router = Router(name="voice_router")


@router.message(F.voice)
async def handle_voice_message(
    message: Message,
    bot: Bot,
    config: BotConfig,
    normahub_client: NormaHubClient,
    context_manager: ConversationManager,
) -> None:
    """Download voice note, transcribe with Whisper-1, and stream LLM answer."""
    if not message.voice:
        return

    user_id = message.from_user.id if message.from_user else 0
    status_msg = await message.answer("🎧 *Слушаю и расшифровываю голосовое...*")
    await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VOICE)

    try:
        # 1. Download voice file bytes
        file_info = await bot.get_file(message.voice.file_id)
        if not file_info.file_path:
            await status_msg.edit_text("❌ Не удалось получить путь к голосовому файлу.")
            return

        audio_buffer = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=audio_buffer)
        audio_bytes = audio_buffer.getvalue()

        # 2. Transcribe using NormaHub Whisper endpoint
        transcribed_text = await normahub_client.transcribe_audio(
            audio_bytes=audio_bytes,
            filename="voice.ogg",
            model="whisper-1",
        )

        if not transcribed_text or not transcribed_text.strip():
            await status_msg.edit_text("🔇 Не удалось распознать речь в голосовом сообщении. Попробуйте еще раз.")
            return

        # 3. Inform user of recognized text
        header_text = f"🗣️ **Распознано:**\n_{transcribed_text.strip()}_\n\n💭 *Генерирую ответ...*"
        await status_msg.edit_text(header_text)

        # 4. Feed into conversation context and stream answer
        context_manager.add_user_message(user_id, transcribed_text)
        model = context_manager.get_model(user_id)

        answer_msg = await message.answer("💭 *Ответ формируется...*")
        debouncer = TelegramStreamDebouncer(
            bot=bot,
            chat_id=message.chat.id,
            message_id=answer_msg.message_id,
            interval=config.stream_debounce_interval,
            parse_mode=ParseMode.MARKDOWN,
        )

        messages_payload = context_manager.get_messages(user_id)
        async for token in normahub_client.stream_chat_completion(
            messages=messages_payload,
            model=model,
        ):
            await debouncer.add_token(token)

        final_answer = await debouncer.flush()
        if final_answer:
            context_manager.add_assistant_message(user_id, final_answer)

    except NormaHubError as e:
        logger.error("NormaHub error in voice processing: %s", e)
        await status_msg.edit_text(f"❌ **Ошибка API при распознавании:** {e.message}")
    except Exception as e:
        logger.exception("Unexpected error processing voice message: %s", e)
        await status_msg.edit_text(f"❌ **Непредвиденная ошибка при обработке войса:** {e}")
