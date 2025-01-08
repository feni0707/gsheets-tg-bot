from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from datetime import datetime

from utils.async_redis import AsyncRedis
from handlers.user import db

# from utils.utils import delete_last_day_photos


class CatchRequestsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        msg = data["event_from_user"]
        redis = AsyncRedis()
        if await db.user_exists(msg.id):
            any_activ_today = await redis.was_there_activity_today(msg.id, any=True)
            if not any_activ_today:
                await db.update_last_action_date(msg.id)
            person_type = await db.get_person_type(msg.id)
            if not await db.exist_daily_record():
                # index_now_weekday = datetime.today().weekday()
                # if index_now_weekday:
                #     delete_last_day_photos()
                await db.add_daily_record()
            await db.increment_daily_statistic(person_type, not any_activ_today)

        return await handler(event, data)
        now_state = data.get("state", None)
