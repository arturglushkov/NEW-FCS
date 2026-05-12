"""FCS Bot — main entry point"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
import sqlalchemy as sa

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.config.settings import settings
from app.core.database.engine import engine, Base
from app.bot.handlers.handlers import router
from app.models.models import User, SiteObject, Shift, Task

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def init_db() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database ready ✅")
    except Exception as e:
        logger.error(f"DB error: {e}")
        raise


async def main() -> None:
    logger.info("Starting FCS Bot...")

    await init_db()

    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("FCS Bot started ✅")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await engine.dispose()
        await bot.session.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
