"""Text messages chat handler with typing indicator and streaming via debouncer."""

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction, ParseMode
from aiogram.types import Message

from bot.client.normahub import (
    NormaHubAuthError,
    NormaHubBalanceError,
    NormaHubClient,
    NormaHubRateLimitError,
)
from bot.config import BotConfig
from bot.database.db import DatabaseManager
from bot.keyboards.inline import get_balance_keyboard
from bot.utils.context import ConversationManager
from bot.utils.debouncer import TelegramStreamDebouncer

logger = logging.getLogger(__name__)
router = Router(name="chat_router")


async def _keep_typing(bot: Bot, chat_id: int, stop_event: asyncio.Event) -> None:
    """Periodically emit 'typing' chat action every 4 seconds until stopped."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except TimeoutError:
            pass


@router.message(F.text, ~F.text.startswith("/"))
async def handle_chat_message(
    message: Message,
    bot: Bot,
    config: BotConfig,
    normahub_client: NormaHubClient,
    context_manager: ConversationManager,
    db: DatabaseManager | None = None,
) -> None:
    """Stream response from NormaHub LLM directly to Telegram message."""
    user_id = message.from_user.id if message.from_user else 0
    prompt = message.text or ""

    # Credit balance verification
    if db:
        has_credit = await db.deduct_credit(user_id, 1)
        if not has_credit:
            from bot.handlers.stars import get_stars_shop_keyboard

            await message.answer(
                "⭐ **У вас закончились доступные запросы!**\n\n"
                "Пополните баланс в 1 клик через Telegram Stars или пригласите коллегу "
                "через команду `/ref` (+5 бонусных запросов за каждого друга):",
                reply_markup=get_stars_shop_keyboard(),
            )
            return

    # Register user message into conversation history
    context_manager.add_user_message(user_id, prompt)
    model = context_manager.get_model(user_id)

    # Initial placeholder message
    placeholder_msg = await message.answer("💭 *Генерирую ответ...*")

    # Start typing indicator loop
    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(bot, message.chat.id, stop_typing))


    debouncer = TelegramStreamDebouncer(
        bot=bot,
        chat_id=message.chat.id,
        message_id=placeholder_msg.message_id,
        interval=config.stream_debounce_interval,
        parse_mode=ParseMode.MARKDOWN,
    )

    try:
        messages_payload = context_manager.get_messages(user_id)
        async for token in normahub_client.stream_chat_completion(
            messages=messages_payload,
            model=model,
        ):
            await debouncer.add_token(token)

        final_text = await debouncer.flush()
        if final_text:
            context_manager.add_assistant_message(user_id, final_text)
        else:
            await placeholder_msg.edit_text("⚠️ Ответ от модели пуст. Попробуйте переформулировать запрос.")

    except NormaHubBalanceError as e:
        if db:
            await db.add_credits(user_id, 1)
        logger.warning("NormaHub balance error: %s", e)
        await placeholder_msg.edit_text(
            "💳 **Недостаточно средств на балансе NormaHub.**\n\n"
            "Пополните баланс в личном кабинете для продолжения диалога:",
            reply_markup=get_balance_keyboard(),
        )
    except NormaHubAuthError as e:
        if db:
            await db.add_credits(user_id, 1)
        logger.error("NormaHub authentication failed: %s", e)
        await placeholder_msg.edit_text(
            "🔑 **Ошибка авторизации NormaHub.**\n\n"
            "Убедитесь, что `NORMAHUB_API_KEY` в конфигурации указан корректно.",
        )
    except NormaHubRateLimitError as e:
        if db:
            await db.add_credits(user_id, 1)
        logger.warning("NormaHub rate limit: %s", e)
        await placeholder_msg.edit_text(
            "⏳ **Превышен лимит запросов.**\nПожалуйста, подождите несколько секунд и попробуйте снова.",
        )
    except Exception as e:
        if db:
            await db.add_credits(user_id, 1)
        logger.exception("Unexpected error in chat streaming: %s", e)
        await placeholder_msg.edit_text(
            f"❌ **Произошла ошибка при обработке запроса:**\n`{e}`\n\n"
            "Попробуйте повторить запрос позже или смените модель через `/model`.",
        )

    finally:
        stop_typing.set()
        await typing_task
