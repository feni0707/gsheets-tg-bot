from sys import path
import asyncio
from logging import getLogger, basicConfig, INFO, info
from datetime import date

# import aioredis
from redis.asyncio.client import Redis
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage

from handlers import user
from data import config

from middlewares.admin import AdminMiddleware
from middlewares.catch_requests import CatchRequestsMiddleware
from utils.google_sheets import GoogleTable
from utils.async_redis import AsyncRedis


path.append("..")
logger = getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
redis = Redis(host="localhost")
storage = RedisStorage(redis=redis)
dp = Dispatcher(storage=storage)


async def main() -> None:
    basicConfig(
        level=INFO,
        # format="%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s",
        format="%(asctime)s - [%(levelname)s] -  %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s",
        filename=f"logs/{date.today()}.log",
    )

    info("Starting bot")

    # dp.message.middleware.register(AdminMiddleware())
    dp.message.middleware.register(CatchRequestsMiddleware())
    dp.include_router(user.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    school_schedule_1_shift = GoogleTable(
        "data/credentials.json",
        "1ajP6yOJX8QxYgcbG9HCkRpqiDS81pphIBju9a_HBMbk",
        1,
    )

    school_schedule_2_shift = GoogleTable(
        "data/credentials.json",
        "1HTUYHHvPxBLZyUbcl2RCLCqn_WXJfCmTL8HaC7AFNQA",
        2,
    )
    loop = asyncio.get_event_loop()

    asyncio.ensure_future(main())
    asyncio.ensure_future(school_schedule_1_shift.start_polling())
    asyncio.ensure_future(school_schedule_2_shift.start_polling())

    loop.run_forever()
