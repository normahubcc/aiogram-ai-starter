"""Telegram Stars native monetization handlers (XTR currency)."""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)

from bot.database.db import DatabaseManager

logger = logging.getLogger(__name__)
router = Router(name="stars_router")

PACKAGES = {
    "pack_100": {
        "title": "⚡ 100 AI запросов",
        "desc": "100 генераций к Claude Sonnet 5.5, DeepSeek v4.1 и SeeDance 2.5",
        "stars": 10,
        "credits": 100,
    },
    "pack_500": {
        "title": "🚀 500 AI запросов (Скидка 10%)",
        "desc": "500 генераций для активных разработчиков и задач",
        "stars": 45,
        "credits": 500,
    },
    "pack_2000": {
        "title": "💎 2000 AI запросов (Скидка 25%)",
        "desc": "2000 генераций для команд и сложных пайплайнов",
        "stars": 150,
        "credits": 2000,
    },
}


def get_stars_shop_keyboard() -> InlineKeyboardMarkup:
    """Build shop inline keyboard with Telegram Stars packages."""
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{pkg['title']} — ⭐ {pkg['stars']} Stars",
                callback_data=f"buy_pack:{key}",
            )
        ]
        for key, pkg in PACKAGES.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("buy"))
async def handle_buy_command(message: Message, db: DatabaseManager) -> None:
    """Show Telegram Stars package catalog."""
    user = await db.get_or_create_user(
        message.from_user.id if message.from_user else 0,
        message.from_user.username if message.from_user else None,
        message.from_user.first_name if message.from_user else None,
    )
    current_balance = user.get("balance_credits", 0)

    text = (
        "⭐ **Пополнение баланса через Telegram Stars**\n\n"
        f"Ваш текущий баланс: **{current_balance} запросов**.\n\n"
        "Stars (⭐) — официальная цифровая валюта Telegram. Покупка происходит мгновенно "
        "в 1 клик через App Store, Google Play или Telegram Web без ввода банковских карт!\n\n"
        "Выберите желаемый пакет:"
    )
    await message.answer(text, reply_markup=get_stars_shop_keyboard())


@router.callback_query(F.data.startswith("buy_pack:"))
async def handle_buy_package_callback(callback: CallbackQuery) -> None:
    """Send Telegram invoice for the selected Stars package."""
    pack_key = callback.data.split(":", 1)[1] if callback.data else ""
    pkg = PACKAGES.get(pack_key)

    if not pkg:
        await callback.answer("Пакет не найден.", show_alert=True)
        return

    await callback.answer()

    if isinstance(callback.message, Message):
        prices = [LabeledPrice(label=pkg["title"], amount=pkg["stars"])]
        await callback.message.answer_invoice(
            title=pkg["title"],
            description=pkg["desc"],
            payload=pack_key,
            currency="XTR",  # Telegram Stars
            prices=prices,
        )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery) -> None:
    """Approve checkout query before Telegram initiates charge."""
    # Validate payload is one of our packages
    if pre_checkout_query.invoice_payload in PACKAGES:
        await pre_checkout_query.answer(ok=True)
    else:
        await pre_checkout_query.answer(
            ok=False,
            error_message="Неизвестный пакет запросов. Попробуйте снова через /buy.",
        )


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, db: DatabaseManager) -> None:
    """Process confirmed Telegram Stars payment and credit user balance."""
    payment = message.successful_payment
    if not payment:
        return

    pack_key = payment.invoice_payload
    pkg = PACKAGES.get(pack_key)
    if not pkg:
        logger.error("Unknown invoice payload in successful payment: %s", pack_key)
        return

    user_id = message.from_user.id if message.from_user else 0
    stars_amount = payment.total_amount
    credits_to_add = pkg["credits"]
    charge_id = payment.telegram_payment_charge_id

    success = await db.record_stars_payment(
        user_id=user_id,
        stars_amount=stars_amount,
        credits_added=credits_to_add,
        charge_id=charge_id,
    )

    if success:
        user = await db.get_user(user_id)
        new_balance = user["balance_credits"] if user else credits_to_add

        text = (
            "🎉 **Оплата успешно завершена!**\n\n"
            f"Вам начислено: **+{credits_to_add} запросов**.\n"
            f"Текущий баланс: **{new_balance} запросов**.\n\n"
            "Все модели (Claude Sonnet 5.5, DeepSeek v4.1, SeeDance 2.5) готовы к работе. "
            "Приятного использования!"
        )
        await message.answer(text)
    else:
        await message.answer("⚠️ Платеж уже был обработан ранее.")
