"""Viral referral engine handlers."""

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.database.db import DatabaseManager

logger = logging.getLogger(__name__)
router = Router(name="referral_router")


@router.message(Command("ref"))
async def handle_referral_command(message: Message, bot: Bot, db: DatabaseManager) -> None:
    """Show personal referral link, stats, and 1-click share button."""
    user_id = message.from_user.id if message.from_user else 0
    bot_info = await bot.get_me()
    bot_username = bot_info.username or "normahub_bot"

    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    stats = await db.get_referral_stats(user_id)

    share_text = (
        "🚀 Попробуй бота на Claude Sonnet 5.5 и DeepSeek v4.1 без VPN и зарубежных карт! "
        "Переходи по ссылке и получи +15 бесплатных запросов:"
    )
    share_url = f"https://t.me/share/url?url={ref_link}&text={share_text}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📲 Поделиться ссылкой с коллегами",
                    url=share_url,
                )
            ]
        ]
    )

    text = (
        "🎁 **Реферальная программа NormaHub**\n\n"
        "Приглашайте разработчиков и получайте бонусные запросы к нейросетям!\n\n"
        "• **Ваш друг получает:** +15 бесплатных запросов при старте (вместо стандартных 10).\n"
        "• **Вы получаете:** +5 запросов за каждого приглашенного пользователя.\n\n"
        "📊 **Ваша статистика:**\n"
        f"• Приглашено друзей: **{stats['total_invited']}**\n"
        f"• Заработано бонусов: **+{stats['total_earned']} запросов**\n\n"
        f"🔗 **Ваша персональная ссылка:**\n`{ref_link}`"
    )

    await message.answer(text, reply_markup=keyboard)
