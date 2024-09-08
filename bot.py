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


async def main() -> None:
    basicConfig(
        level=INFO,
        # format="%(filename)s:%(lineno)d #%(levelname)-8s [%(asctime)s] - %(name)s - %(message)s",
        format="%(asctime)s - [%(levelname)s] -  %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s",
        filename=f"logs/{date.today()}.log",
    )

    info("Starting bot")

    redis = Redis(host="localhost")

    storage = RedisStorage(redis=redis)

    dp = Dispatcher(storage=storage)

    dp.message.middleware.register(AdminMiddleware())
    dp.message.middleware.register(CatchRequestsMiddleware())
    dp.include_router(user.router)

    # await redis_db.set_bot(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    # asyncio.run(main())
    # "12Tl6P67Ed1YNVFqlLVER6BJcicn5tUr2ae_CtbawQYs",
    school_schedule_1_shift = GoogleTable(
        "credentials.json",
        "1ajP6yOJX8QxYgcbG9HCkRpqiDS81pphIBju9a_HBMbk",
        1,
    )

    school_schedule_2_shift = GoogleTable(
        "credentials.json",
        "1HTUYHHvPxBLZyUbcl2RCLCqn_WXJfCmTL8HaC7AFNQA",
        2,
    )
    loop = asyncio.get_event_loop()

    asyncio.ensure_future(main())
    asyncio.ensure_future(school_schedule_1_shift.start_polling())
    asyncio.ensure_future(school_schedule_2_shift.start_polling())

    # loop.run_until_complete(db.create_pool())
    loop.run_forever()
