"""Common command handlers: /start, /help, /clear, /balance."""

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from bot.client.normahub import NormaHubClient
from bot.keyboards.inline import (
    get_balance_keyboard,
    get_quick_actions_keyboard,
)
from bot.utils.context import ConversationManager

logger = logging.getLogger(__name__)
router = Router(name="common_router")


@router.message(CommandStart())
async def handle_start(message: Message, context_manager: ConversationManager) -> None:
    """Handle /start command with rich welcome overview."""
    user_name = message.from_user.first_name if message.from_user else "друг"
    current_model = context_manager.get_model(message.from_user.id if message.from_user else 0)

    text = (
        f"👋 **Привет, {user_name}!**\n\n"
        "Я — готовый продакшн-бот на **aiogram 3**, работающий через единый шлюз **NormaHub AI Gateway**.\n\n"
        "✨ **Что я умею:**\n"
        "• ⚡ **Быстрый стриминг ответов:** вывод токенов в реальном времени (~800ms debounce).\n"
        "• 🧠 **Смена моделей:** DeepSeek v4.1 Flash, Claude Sonnet 5.5 и другие.\n"
        "• 🎬 **Генерация видео:** SeeDance 2.5 через команду `/video <описание>`.\n"
        "• 🎙️ **Голосовые сообщения:** автоматическая транскрипция (Whisper) и ответ в чат.\n"
        "• 💾 **Умная память:** сохранение контекста беседы (до 10 сообщений).\n\n"
        f"Текущая модель: `{current_model}`\n\n"
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
async def handle_balance(message: Message, normahub_client: NormaHubClient) -> None:
    """Handle /balance command showing connection and account status."""
    loading_msg = await message.answer("⏳ *Проверяю статус шлюза и баланс NormaHub...*")
    try:
        data = await normahub_client.check_balance()
        status = data.get("status", "operational")
        models_count = data.get("active_models_count", 30)

        reply_text = (
            "💳 **Статус подключения NormaHub API:**\n\n"
            f"• Состояние шлюза: **{status.upper()}** ✅\n"
            f"• Доступных моделей: **{models_count}+**\n"
            "• Прямая маршрутизация по РФ: **Включена** 🚀\n"
            "• Единый баланс: Рубли (СБП / МИР)\n\n"
            "Детализация расходов и пополнение доступны в личном кабинете:"
        )
        await loading_msg.edit_text(reply_text, reply_markup=get_balance_keyboard())
    except Exception as e:
        logger.error("Failed to check balance: %s", e)
        await loading_msg.edit_text(
            f"⚠️ *Не удалось получить информацию о балансе:* {e}\n\n"
            "Проверьте настройки API-ключа в `.env`.",
            reply_markup=get_balance_keyboard(),
        )


@router.callback_query(F.data == "clear_context")
async def callback_clear_context(callback: CallbackQuery, context_manager: ConversationManager) -> None:
    """Callback for quick context clearing."""
    if callback.from_user:
        context_manager.clear(callback.from_user.id)
    await callback.answer("Память диалога очищена!", show_alert=True)
    if callback.message:
        await callback.message.answer("🧹 **Контекст очищен.** Можно задавать новый вопрос!")


@router.callback_query(F.data == "check_balance")
async def callback_check_balance(callback: CallbackQuery, normahub_client: NormaHubClient) -> None:
    """Callback for balance checking."""
    await callback.answer()
    if callback.message:
        await handle_balance(callback.message, normahub_client)
