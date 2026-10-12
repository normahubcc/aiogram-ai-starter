"""Video generation handler (/video <prompt>) using SeeDance 2.5."""

import asyncio
import logging
import time

from aiogram import Bot, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from bot.client.normahub import NormaHubClient, NormaHubError

logger = logging.getLogger(__name__)
router = Router(name="video_router")


@router.message(Command("video"))
async def handle_video_command(
    message: Message,
    command: CommandObject,
    bot: Bot,
    normahub_client: NormaHubClient,
) -> None:
    """Generate AI video via SeeDance 2.5."""
    prompt = command.args
    if not prompt or not prompt.strip():
        await message.answer(
            "🎬 **Генерация видео нейросетью SeeDance 2.5**\n\n"
            "Пожалуйста, укажите описание видео после команды.\n"
            "**Пример использования:**\n"
            "`/video Футуристический киберпанк-город под ночным неоновым дождем, 4k cinematic`\n\n"
            "💡 Генерация обычно занимает от 1 до 3 минут."
        )
        return

    status_msg = await message.answer(
        "🎬 **Задача отправлена в очередь SeeDance 2.5...**\n"
        "⏳ Инициализация генерации кадра..."
    )

    try:
        task_data = await normahub_client.create_video_task(
            prompt=prompt.strip(),
            model="seedance-2.5",
            duration=5,
            aspect_ratio="16:9",
        )
        task_id = task_data.get("id") or task_data.get("task_id")
        if not task_id:
            await status_msg.edit_text("❌ Сервер не вернул идентификатор задачи генерации.")
            return

        start_time = time.monotonic()
        poll_interval = 4.0
        max_duration = 360.0  # 6 minutes

        while time.monotonic() - start_time < max_duration:
            elapsed = int(time.monotonic() - start_time)
            await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.RECORD_VIDEO)

            status_info = await normahub_client.get_video_status(str(task_id))
            status = status_info.get("status", "processing")

            if status == "completed":
                video_url = status_info.get("video_url") or status_info.get("url")
                if not video_url:
                    await status_msg.edit_text("❌ Ошибка: видео сгенерировано, но URL отсутствует.")
                    return

                await status_msg.edit_text("✨ **Видео готово! Загружаю в Telegram...**")
                await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO)

                caption = (
                    "🎬 **SeeDance 2.5 Video**\n\n"
                    f"📝 *Промпт:* {prompt[:300]}\n"
                    f"⏱️ Время генерации: {elapsed}с"
                )
                await bot.send_video(
                    chat_id=message.chat.id,
                    video=video_url,
                    caption=caption,
                )
                try:
                    await status_msg.delete()
                except Exception:
                    pass
                return

            if status == "failed":
                err = status_info.get("error") or "Неизвестная ошибка на стороне провайдера"
                await status_msg.edit_text(f"❌ **Генерация не удалась:** {err}")
                return

            # Update progress status message every ~16 seconds to respect rate limits
            if elapsed > 0 and elapsed % 16 < poll_interval:
                try:
                    await status_msg.edit_text(
                        "🎬 **Генерация SeeDance 2.5 в процессе...**\n"
                        f"⏳ Прошло: **{elapsed} сек.**\n"
                        "Нейросеть рендерит кадры и физику движения."
                    )
                except Exception:
                    pass

            await asyncio.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.15, 8.0)

        await status_msg.edit_text("⌛ Превышено время ожидания генерации видео (таймаут). Попробуйте позже.")

    except NormaHubError as e:
        logger.error("NormaHub error in video generation: %s", e)
        await status_msg.edit_text(f"❌ **Ошибка NormaHub API:** {e.message}")
    except Exception as e:
        logger.exception("Unexpected error during video generation: %s", e)
        await status_msg.edit_text(f"❌ **Непредвиденная ошибка:** {e}")
