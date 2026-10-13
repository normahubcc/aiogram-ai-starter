"""Persistent SQLite storage with WAL mode, auto-migrations, and transactional operations."""

import logging
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Async SQLite database manager optimized for production high concurrency."""

    def __init__(self, db_path: str | Path = "data/bot_database.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    async def init_db(self) -> None:
        """Create tables, indexes, and configure PRAGMA parameters for WAL concurrency."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode = WAL;")
            await db.execute("PRAGMA synchronous = NORMAL;")
            await db.execute("PRAGMA busy_timeout = 5000;")

            # 1. Users Table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    balance_credits INTEGER NOT NULL DEFAULT 10,
                    selected_model TEXT NOT NULL DEFAULT 'deepseek-v4.1-flash',
                    referrer_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )

            # 2. Transactions Table (Telegram Stars Purchases)
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    stars_amount INTEGER NOT NULL,
                    credits_added INTEGER NOT NULL,
                    telegram_charge_id TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                );
                """
            )

            # 3. Referrals Table
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    referrer_id INTEGER NOT NULL,
                    referred_id INTEGER NOT NULL UNIQUE,
                    bonus_credited INTEGER NOT NULL DEFAULT 5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (referrer_id) REFERENCES users (user_id),
                    FOREIGN KEY (referred_id) REFERENCES users (user_id)
                );
                """
            )

            # Indexes for fast lookup
            await db.execute("CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer_id);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_tx_user ON transactions(user_id);")
            await db.commit()
            logger.info("Database initialized successfully at %s (WAL mode enabled)", self.db_path)

    async def get_or_create_user(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
        referrer_id: int | None = None,
    ) -> dict[str, Any]:
        """Fetch existing user or register a new one, awarding welcome and referral bonuses."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()

            if row:
                # Update username or first_name if changed
                await db.execute(
                    "UPDATE users SET username = ?, first_name = ? WHERE user_id = ?",
                    (username, first_name, user_id),
                )
                await db.commit()
                return dict(row)

            # Register new user with 10 free trial credits
            initial_credits = 10
            actual_referrer = referrer_id if (referrer_id and referrer_id != user_id) else None

            # Check if referrer exists
            if actual_referrer:
                ref_cur = await db.execute("SELECT user_id FROM users WHERE user_id = ?", (actual_referrer,))
                if not await ref_cur.fetchone():
                    actual_referrer = None

            await db.execute(
                """
                INSERT INTO users (user_id, username, first_name, balance_credits, referrer_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, username, first_name, initial_credits, actual_referrer),
            )

            # Credit referral bonus (5 credits to referrer, +5 extra to new user)
            if actual_referrer:
                bonus = 5
                await db.execute(
                    "UPDATE users SET balance_credits = balance_credits + ? WHERE user_id = ?",
                    (bonus, actual_referrer),
                )
                await db.execute(
                    "UPDATE users SET balance_credits = balance_credits + ? WHERE user_id = ?",
                    (bonus, user_id),
                )
                await db.execute(
                    """
                    INSERT OR IGNORE INTO referrals (referrer_id, referred_id, bonus_credited)
                    VALUES (?, ?, ?)
                    """,
                    (actual_referrer, user_id, bonus),
                )
                initial_credits += bonus

            await db.commit()

            return {
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "balance_credits": initial_credits,
                "selected_model": "deepseek-v4.1-flash",
                "referrer_id": actual_referrer,
            }

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        """Retrieve user record by Telegram ID."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_selected_model(self, user_id: int, model: str) -> None:
        """Save preferred AI model for user."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("UPDATE users SET selected_model = ? WHERE user_id = ?", (model, user_id))
            await db.commit()

    async def deduct_credit(self, user_id: int, amount: int = 1) -> bool:
        """Deduct generation credit atomically. Returns True if successful, False if insufficient balance."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "UPDATE users SET balance_credits = balance_credits - ? WHERE user_id = ? AND balance_credits >= ?",
                (amount, user_id, amount),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def add_credits(self, user_id: int, amount: int) -> int:
        """Add credits to user account. Returns new balance."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "UPDATE users SET balance_credits = balance_credits + ? WHERE user_id = ? RETURNING balance_credits",
                (amount, user_id),
            )
            row = await cursor.fetchone()
            await db.commit()
            return row["balance_credits"] if row else 0

    async def record_stars_payment(
        self,
        user_id: int,
        stars_amount: int,
        credits_added: int,
        charge_id: str,
    ) -> bool:
        """Record a successful Telegram Stars payment transaction and credit user balance."""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute(
                    """
                    INSERT INTO transactions (user_id, stars_amount, credits_added, telegram_charge_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (user_id, stars_amount, credits_added, charge_id),
                )
                await db.execute(
                    "UPDATE users SET balance_credits = balance_credits + ? WHERE user_id = ?",
                    (credits_added, user_id),
                )
                await db.commit()
                return True
            except aiosqlite.IntegrityError:
                logger.warning("Duplicate payment transaction charge_id %s ignored", charge_id)
                return False

    async def get_referral_stats(self, user_id: int) -> dict[str, int]:
        """Calculate total referrals count and total bonus credits earned."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT COUNT(*) as total_invited, COALESCE(SUM(bonus_credited), 0) as total_earned "
                "FROM referrals WHERE referrer_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
            return {
                "total_invited": row["total_invited"] if row else 0,
                "total_earned": row["total_earned"] if row else 0,
            }

    async def get_admin_metrics(self) -> dict[str, Any]:
        """Aggregate high-level metrics for /admin command."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            users_cur = await db.execute("SELECT COUNT(*) as total FROM users")
            users_row = await users_cur.fetchone()

            tx_cur = await db.execute(
                "SELECT COUNT(*) as total_tx, COALESCE(SUM(stars_amount), 0) as total_stars FROM transactions"
            )
            tx_row = await tx_cur.fetchone()

            return {
                "total_users": users_row["total"] if users_row else 0,
                "total_transactions": tx_row["total_tx"] if tx_row else 0,
                "total_stars_earned": tx_row["total_stars"] if tx_row else 0,
            }

    async def get_all_user_ids(self) -> list[int]:
        """Retrieve all registered user IDs for admin broadcasts."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
