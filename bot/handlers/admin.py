"""Administrative command handlers: /admin, /broadcast."""

import asyncio
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import BotConfig
from bot.database.db import DatabaseManager

logger = logging.getLogger(__name__)
router = Router(name="admin_router")


@router.message(Command("admin"))
async def handle_admin_dashboard(message: Message, config: BotConfig, db: DatabaseManager) -> None:
    """Display real-time administrative metrics."""
    user_id = message.from_user.id if message.from_user else 0
    if not config.is_admin(user_id):
        await message.answer("⛔ Доступ ограничен. Эта команда доступна только администраторам.")
        return

    metrics = await db.get_admin_metrics()

    text = (
        "👑 **Административная панель NormaHub Bot**\n\n"
        f"👥 Всего зарегистрировано пользователей: **{metrics['total_users']}**\n"
        f"💳 Всего успешных платежей (Stars): **{metrics['total_transactions']}**\n"
        f"⭐ Заработано Telegram Stars: **{metrics['total_stars_earned']} ⭐**\n\n"
        "📢 **Команды рассылки:**\n"
        "• `/broadcast <сообщение>` — безопасная фоновая рассылка всем пользователям с защитой от лимитов Telegram."
    )
    await message.answer(text)


@router.message(Command("broadcast"))
async def handle_broadcast_command(
    message: Message,
    bot: Bot,
    config: BotConfig,
    db: DatabaseManager,
) -> None:
    """Broadcast announcement to all registered users with rate-limiting throttling."""
    user_id = message.from_user.id if message.from_user else 0
    if not config.is_admin(user_id):
        await message.answer("⛔ Доступ ограничен.")
        return

    # Extract text after /broadcast
    parts = message.text.split(maxsplit=1) if message.text else []
    if len(parts) < 2:
        await message.answer("Использование: `/broadcast <текст рассылки>`")
        return

    broadcast_text = parts[1]
    user_ids = await db.get_all_user_ids()

    if not user_ids:
        await message.answer("В базе данных нет пользователей для рассылки.")
        return

    status_msg = await message.answer(f"⏳ Запуск рассылки для {len(user_ids)} пользователей...")

    delivered = 0
    failed = 0

    for target_id in user_ids:
        try:
            await bot.send_message(chat_id=target_id, text=broadcast_text)
            delivered += 1
            # Throttle to adhere to Telegram 30 msgs/second limit
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.debug("Broadcast failed for user %d: %s", target_id, e)
            failed += 1

    await status_msg.edit_text(
        "✅ **Рассылка завершена!**\n\n"
        f"• Доставлено: **{delivered}**\n"
        f"• Ошибок (заблокировали бота/удалены): **{failed}**"
    )
