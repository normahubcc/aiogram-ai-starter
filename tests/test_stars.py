"""Unit tests for Telegram Stars monetization logic."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import PreCheckoutQuery, SuccessfulPayment

from bot.database.db import DatabaseManager
from bot.handlers.stars import (
    PACKAGES,
    get_stars_shop_keyboard,
    process_pre_checkout_query,
    process_successful_payment,
)


def test_packages_structure():
    assert "pack_100" in PACKAGES
    assert PACKAGES["pack_100"]["stars"] == 10
    assert PACKAGES["pack_100"]["credits"] == 100
    assert "pack_500" in PACKAGES
    assert "pack_2000" in PACKAGES

    kb = get_stars_shop_keyboard()
    assert len(kb.inline_keyboard) == 3


@pytest.mark.asyncio
async def test_pre_checkout_query_approval():
    query = MagicMock(spec=PreCheckoutQuery)
    query.invoice_payload = "pack_500"
    query.answer = AsyncMock()

    await process_pre_checkout_query(query)
    query.answer.assert_awaited_once_with(ok=True)


@pytest.mark.asyncio
async def test_pre_checkout_query_rejection():
    query = MagicMock(spec=PreCheckoutQuery)
    query.invoice_payload = "invalid_pack_fake"
    query.answer = AsyncMock()

    await process_pre_checkout_query(query)
    query.answer.assert_awaited_once()
    assert query.answer.call_args.kwargs["ok"] is False


@pytest.mark.asyncio
async def test_successful_payment_processing(tmp_path: Path):
    db_file = tmp_path / "test.db"
    db = DatabaseManager(db_path=db_file)
    await db.init_db()

    message = MagicMock()
    user_mock = MagicMock()
    user_mock.id = 777
    user_mock.username = "payer"
    user_mock.first_name = "John"
    message.from_user = user_mock
    message.answer = AsyncMock()


    payment = MagicMock(spec=SuccessfulPayment)
    payment.invoice_payload = "pack_100"
    payment.total_amount = 10
    payment.telegram_payment_charge_id = "tg_charge_xyz"
    message.successful_payment = payment

    await db.get_or_create_user(user_id=777)
    await process_successful_payment(message, db)

    # Verification
    user = await db.get_user(777)
    assert user["balance_credits"] == 110  # 10 initial + 100
    message.answer.assert_awaited_once()
    assert "Оплата успешно завершена" in message.answer.call_args[0][0]
