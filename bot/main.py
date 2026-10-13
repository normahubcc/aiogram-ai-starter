"""Main entrypoint for NormaHub AI Telegram Bot."""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.client.normahub import NormaHubClient
from bot.config import BotConfig, load_config
from bot.handlers import setup_routers
from bot.middlewares.throttling import ThrottlingMiddleware
from bot.utils.context import ConversationManager

logger = logging.getLogger("bot")


def setup_logging(level_name: str) -> None:
    """Configure structured logging output."""
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


async def main() -> None:
    """Initialize resources and run polling loop."""
    config: BotConfig = load_config()
    setup_logging(config.log_level)

    logger.info("Initializing NormaHub Telegram Bot Starter...")
    logger.info("Default model: %s | Base URL: %s", config.default_model, config.normahub_base_url)

    # 1. Storage setup
    storage = MemoryStorage()
    if config.redis_url:
        try:
            from aiogram.fsm.storage.redis import RedisStorage

            storage = RedisStorage.from_url(config.redis_url)
            logger.info("Connected to Redis storage: %s", config.redis_url)
        except Exception as e:
            logger.warning("Could not connect to Redis (%s), falling back to MemoryStorage", e)

    # 2. Database & Managers
    from bot.database.db import DatabaseManager

    db = DatabaseManager(db_path=config.database_path)
    await db.init_db()

    normahub_client = NormaHubClient(
        api_key=config.normahub_api_key.get_secret_value(),
        base_url=config.normahub_base_url,
    )
    context_manager = ConversationManager(
        default_model=config.default_model,
        default_system_prompt=config.system_prompt,
        max_turns=config.max_context_turns,
    )

    # 3. Bot instance
    # Aiogram 3.7+ uses DefaultBotProperties, while earlier 3.x accepts parse_mode directly
    try:
        from aiogram.client.default import DefaultBotProperties

        default_props = DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        bot = Bot(token=config.bot_token.get_secret_value(), default=default_props)
    except (ImportError, TypeError):
        bot = Bot(token=config.bot_token.get_secret_value())

    # 4. Dispatcher & Routing
    dp = Dispatcher(storage=storage)

    # Register middlewares
    throttling = ThrottlingMiddleware(rate_limit=config.rate_limit_per_second)
    dp.message.middleware(throttling)
    dp.callback_query.middleware(throttling)

    # Register handlers
    dp.include_router(setup_routers())

    # Workflow data injected into every handler
    workflow_data = {
        "config": config,
        "normahub_client": normahub_client,
        "context_manager": context_manager,
        "db": db,
    }


    try:
        bot_user = await bot.get_me()
        logger.info("Bot started successfully as @%s (ID: %d)", bot_user.username, bot_user.id)
        # Delete webhook to prevent conflicts with long polling
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception:
            pass

        await dp.start_polling(bot, **workflow_data)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.exception("Critical error during bot execution: %s", e)
    finally:
        logger.info("Closing bot resources...")
        await normahub_client.close()
        try:
            if hasattr(bot, "session") and hasattr(bot.session, "close"):
                await bot.session.close()
        except Exception:
            pass
        logger.info("Bot shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
