"""Unit tests for DatabaseManager SQLite storage."""

from pathlib import Path

import pytest

from bot.database.db import DatabaseManager


@pytest.mark.asyncio
async def test_database_init_and_user_creation(tmp_path: Path):
    db_file = tmp_path / "test.db"
    db = DatabaseManager(db_path=db_file)
    await db.init_db()

    # Create new user
    user = await db.get_or_create_user(
        user_id=12345,
        username="developer_pro",
        first_name="Alex",
    )
    assert user["user_id"] == 12345
    assert user["balance_credits"] == 10
    assert user["selected_model"] == "deepseek-v4.1-flash"

    # Fetch user
    fetched = await db.get_user(12345)
    assert fetched is not None
    assert fetched["first_name"] == "Alex"


@pytest.mark.asyncio
async def test_database_credit_deduction_and_addition(tmp_path: Path):
    db_file = tmp_path / "test.db"
    db = DatabaseManager(db_path=db_file)
    await db.init_db()

    await db.get_or_create_user(user_id=100)

    # Deduct 5 credits
    ok = await db.deduct_credit(user_id=100, amount=5)
    assert ok is True

    user = await db.get_user(100)
    assert user["balance_credits"] == 5

    # Deduct 6 credits (should fail because balance is 5)
    fail = await db.deduct_credit(user_id=100, amount=6)
    assert fail is False

    # Add credits
    new_bal = await db.add_credits(user_id=100, amount=20)
    assert new_bal == 25


@pytest.mark.asyncio
async def test_database_referrals_and_bonuses(tmp_path: Path):
    db_file = tmp_path / "test.db"
    db = DatabaseManager(db_path=db_file)
    await db.init_db()

    # User 1 is referrer
    u1 = await db.get_or_create_user(user_id=1)
    assert u1["balance_credits"] == 10

    # User 2 joins with referrer_id=1
    u2 = await db.get_or_create_user(user_id=2, referrer_id=1)
    # User 2 gets 10 standard + 5 referral bonus = 15
    assert u2["balance_credits"] == 15

    # User 1 should have received 5 bonus credits (10 + 5 = 15)
    u1_updated = await db.get_user(1)
    assert u1_updated["balance_credits"] == 15

    # Check referral stats
    stats = await db.get_referral_stats(user_id=1)
    assert stats["total_invited"] == 1
    assert stats["total_earned"] == 5


@pytest.mark.asyncio
async def test_database_stars_payment_recording(tmp_path: Path):
    db_file = tmp_path / "test.db"
    db = DatabaseManager(db_path=db_file)
    await db.init_db()

    await db.get_or_create_user(user_id=500)

    # First transaction
    success = await db.record_stars_payment(
        user_id=500,
        stars_amount=45,
        credits_added=500,
        charge_id="ch_tg_stars_9988",
    )
    assert success is True

    user = await db.get_user(500)
    assert user["balance_credits"] == 510  # 10 initial + 500

    # Duplicate transaction ID should be rejected
    dup = await db.record_stars_payment(
        user_id=500,
        stars_amount=45,
        credits_added=500,
        charge_id="ch_tg_stars_9988",
    )
    assert dup is False

    # Check admin metrics
    metrics = await db.get_admin_metrics()
    assert metrics["total_users"] == 1
    assert metrics["total_transactions"] == 1
    assert metrics["total_stars_earned"] == 45
