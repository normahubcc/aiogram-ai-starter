"""Model selection handler with inline keyboard selector."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.inline import AVAILABLE_MODELS, get_models_keyboard
from bot.utils.context import ConversationManager

logger = logging.getLogger(__name__)
router = Router(name="model_router")


@router.message(Command("model"))
async def handle_model_command(message: Message, context_manager: ConversationManager) -> None:
    """Display interactive model selector."""
    user_id = message.from_user.id if message.from_user else 0
    current_model = context_manager.get_model(user_id)

    text = (
        "⚙️ **Выбор активной AI-модели NormaHub:**\n\n"
        f"Текущая модель: `{current_model}`\n\n"
        "Выберите модель из списка ниже для обработки ваших запросов:"
    )
    await message.answer(text, reply_markup=get_models_keyboard(current_model))


@router.callback_query(F.data == "open_models")
async def callback_open_models(callback: CallbackQuery, context_manager: ConversationManager) -> None:
    """Open model selector from quick actions."""
    user_id = callback.from_user.id if callback.from_user else 0
    current_model = context_manager.get_model(user_id)
    text = (
        "⚙️ **Выбор активной AI-модели NormaHub:**\n\n"
        f"Текущая модель: `{current_model}`\n\n"
        "Выберите модель из списка ниже:"
    )
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(text, reply_markup=get_models_keyboard(current_model))


@router.callback_query(F.data.startswith("select_model:"))
async def callback_select_model(callback: CallbackQuery, context_manager: ConversationManager) -> None:
    """Handle model button click, save preference, update keyboard checkmark."""
    if not callback.data:
        return

    model_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id if callback.from_user else 0

    valid_ids = {m[0] for m in AVAILABLE_MODELS}
    if model_id not in valid_ids:
        await callback.answer("⚠️ Неизвестная модель.", show_alert=True)
        return

    context_manager.set_model(user_id, model_id)
    model_name = next((m[1] for m in AVAILABLE_MODELS if m[0] == model_id), model_id)

    await callback.answer(f"✅ Модель переключена на {model_name}")

    if callback.message:
        text = (
            f"✅ **Активная модель изменена на {model_name}!**\n\n"
            f"Идентификатор: `{model_id}`\n"
            "Все последующие вопросы будут отправляться в эту модель."
        )
        try:
            await callback.message.edit_text(text, reply_markup=get_models_keyboard(model_id))
        except Exception:
            pass


@router.callback_query(F.data == "refresh_models")
async def callback_refresh_models(callback: CallbackQuery, context_manager: ConversationManager) -> None:
    """Refresh model list markup."""
    user_id = callback.from_user.id if callback.from_user else 0
    current_model = context_manager.get_model(user_id)
    await callback.answer("Список обновлен")
    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=get_models_keyboard(current_model))
        except Exception:
            pass
