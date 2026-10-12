"""Inline keyboard builders for model selection and common actions."""


from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

AVAILABLE_MODELS: list[tuple[str, str, str]] = [
    (
        "deepseek-v4.1-flash",
        "DeepSeek v4.1 Flash",
        "⚡ Ультра-быстрый & Экономичный",
    ),
    (
        "claude-sonnet-5-5",
        "Claude Sonnet 5.5",
        "🧠 Флагманский разум & Архитектура",
    ),
]


def get_models_keyboard(current_model: str) -> InlineKeyboardMarkup:
    """Generate keyboard for choosing active AI model with checkmark indicator."""
    builder = InlineKeyboardBuilder()

    for model_id, name, desc in AVAILABLE_MODELS:
        is_active = model_id == current_model
        prefix = "✅ " if is_active else "⚪ "
        button_text = f"{prefix}{name} ({desc})"
        builder.button(
            text=button_text,
            callback_data=f"select_model:{model_id}",
        )

    builder.button(
        text="🔄 Обновить список",
        callback_data="refresh_models",
    )
    builder.adjust(1)
    return builder.as_markup()


def get_quick_actions_keyboard() -> InlineKeyboardMarkup:
    """Generate quick action buttons beneath welcome and help messages."""
    builder = InlineKeyboardBuilder()
    builder.button(text="⚙️ Сменить модель", callback_data="open_models")
    builder.button(text="💳 Баланс API", callback_data="check_balance")
    builder.button(text="🧹 Очистить память", callback_data="clear_context")
    builder.button(text="🌐 Личный кабинет", url="https://normahub.cc/dashboard")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def get_balance_keyboard() -> InlineKeyboardMarkup:
    """Generate balance overview action buttons."""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Пополнить баланс (СБП/РФ)", url="https://normahub.cc/dashboard")
    builder.button(text="📋 Каталог моделей", url="https://normahub.cc/models")
    builder.adjust(1)
    return builder.as_markup()
