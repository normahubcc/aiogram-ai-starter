"""Common command handlers: /start, /help, /clear, /balance."""

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.client.normahub import NormaHubClient
from bot.database.db import DatabaseManager
from bot.keyboards.inline import (
    get_balance_keyboard,
    get_quick_actions_keyboard,
)
from bot.utils.context import ConversationManager

logger = logging.getLogger(__name__)
router = Router(name="common_router")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    context_manager: ConversationManager,
    db: DatabaseManager | None = None,
) -> None:
    """Handle /start command with rich welcome overview and referral onboarding."""
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "друг"
    current_model = context_manager.get_model(user_id)

    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        param = message.text.split()[1]
        if param.startswith("ref_"):
            try:
                referrer_id = int(param.replace("ref_", ""))
            except ValueError:
                pass

    user_credits = 10
    bonus_note = ""
    if db:
        user_record = await db.get_or_create_user(
            user_id=user_id,
            username=message.from_user.username if message.from_user else None,
            first_name=message.from_user.first_name if message.from_user else None,
            referrer_id=referrer_id,
        )
        user_credits = user_record.get("balance_credits", 10)
        if referrer_id and user_record.get("referrer_id") == referrer_id:
            bonus_note = "\n🎁 *Вам начислен повышенный бонус +15 запросов по реферальной ссылке!*"

    text = (
        f"👋 **Привет, {user_name}!**\n\n"
        "Я — готовый продакшн-бот на **aiogram 3**, работающий через единый шлюз **NormaHub AI Gateway**.\n\n"
        "✨ **Что я умею:**\n"
        "• ⚡ **Быстрый стриминг ответов:** вывод токенов в реальном времени (~800ms debounce).\n"
        "• 🧠 **Смена моделей:** DeepSeek v4.1 Flash, Claude Sonnet 5.5 и другие.\n"
        "• 🎬 **Генерация видео:** SeeDance 2.5 через команду `/video <описание>`.\n"
        "• 🎙️ **Голосовые сообщения:** автоматическая транскрипция (Whisper) и ответ в чат.\n"
        "• ⭐ **Telegram Stars:** нативная оплата пакетов запросов в 1 клик (`/buy`).\n"
        "• 🎁 **Реферальный движок:** бонусные генерации за приглашенных друзей (`/ref`).\n\n"
        f"💳 Баланс: **{user_credits} запросов**{bonus_note}\n"
        f"🤖 Активная модель: `{current_model}`\n\n"
        "Просто напиши мне любой вопрос или отправь голосовое!"
    )
    await message.answer(text, reply_markup=get_quick_actions_keyboard())



@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    """Handle /help command with command reference."""
    text = (
        "📖 **Справка по командам NormaHub Bot:**\n\n"
        "• `/start` — Главное меню и статус бота\n"
        "• `/model` — Выбрать активную модель (DeepSeek / Claude)\n"
        "• `/buy` — ⭐ Пополнить баланс через Telegram Stars в 1 клик\n"
        "• `/ref` — 🎁 Ваша реферальная ссылка и статистика приглашений\n"
        "• `/clear` — Очистить историю диалога (сброс памяти)\n"
        "• `/balance` — Проверить статус API и баланс NormaHub\n"
        "• `/video <промпт>` — Сгенерировать видео через SeeDance 2.5\n"
        "• 🎙️ **Голосовое сообщение** — Отправьте войс, бот расшифрует и ответит\n\n"
        "💡 *NormaHub предоставляет единый API для всех мировых нейросетей без VPN, "
        "с посекундным биллингом и оплатой картами РФ/СБП.*"
    )
    await message.answer(text, reply_markup=get_quick_actions_keyboard())


@router.message(Command("clear"))
async def handle_clear(message: Message, context_manager: ConversationManager) -> None:
    """Handle /clear command to reset dialog turns."""
    if message.from_user:
        context_manager.clear(message.from_user.id)
    await message.answer("🧹 **Память диалога успешно очищена!**\nСледующий вопрос начнет новый диалог.")


@router.message(Command("balance"))
async def handle_balance(
    message: Message,
    normahub_client: NormaHubClient,
    db: DatabaseManager | None = None,
) -> None:
    """Handle /balance command showing connection and account status."""
    user_id = message.from_user.id if message.from_user else 0
    loading_msg = await message.answer("⏳ *Проверяю статус шлюза и баланс...*")

    user_credits = 10
    if db:
        user = await db.get_user(user_id)
        if user:
            user_credits = user.get("balance_credits", 10)

    try:
        data = await normahub_client.check_balance()
        status = data.get("status", "operational")
        models_count = data.get("active_models_count", 30)

        reply_text = (
            "💳 **Ваш аккаунт и статус NormaHub API:**\n\n"
            f"• Доступно запросов у вас: **{user_credits}** ⚡\n"
            f"• Состояние шлюза: **{status.upper()}** ✅\n"
            f"• Доступных моделей в шлюзе: **{models_count}+**\n"
            "• Прямая маршрутизация по РФ: **Включена** 🚀\n"
            "• Пополнение: Telegram Stars (⭐) или СБП / МИР на сайте.\n\n"
            "Выберите способ пополнения:"
        )
        await loading_msg.edit_text(reply_text, reply_markup=get_balance_keyboard())
    except Exception as e:
        logger.error("Failed to check balance: %s", e)
        await loading_msg.edit_text(
            f"⚠️ *Не удалось получить информацию о балансе:* {e}\n\n"
            f"• Ваши локальные запросы: **{user_credits}**\n"
            "Проверьте настройки API-ключа в `.env`.",
            reply_markup=get_balance_keyboard(),
        )


@router.callback_query(F.data == "clear_context")
async def callback_clear_context(callback: CallbackQuery, context_manager: ConversationManager) -> None:
    """Callback for quick context clearing."""
    if callback.from_user:
        context_manager.clear(callback.from_user.id)
    await callback.answer("Память диалога очищена!", show_alert=True)
    if callback.message and isinstance(callback.message, Message):
        await callback.message.answer("🧹 **Контекст очищен.** Можно задавать новый вопрос!")


@router.callback_query(F.data == "check_balance")
async def callback_check_balance(
    callback: CallbackQuery,
    normahub_client: NormaHubClient,
    db: DatabaseManager | None = None,
) -> None:
    """Callback for balance checking."""
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        await handle_balance(callback.message, normahub_client, db)


@router.callback_query(F.data == "open_shop")
async def callback_open_shop(callback: CallbackQuery, db: DatabaseManager) -> None:
    """Callback to open Stars shop."""
    await callback.answer()
    if callback.message and isinstance(callback.message, Message):
        from bot.handlers.stars import handle_buy_command

        await handle_buy_command(callback.message, db)


@router.callback_query(F.data == "open_ref")
async def callback_open_ref(callback: CallbackQuery, db: DatabaseManager) -> None:
    """Callback to open referral dashboard."""
    await callback.answer()
    if callback.message and isinstance(callback.message, Message) and callback.bot:
        from bot.handlers.referral import handle_referral_command

        await handle_referral_command(callback.message, callback.bot, db)

