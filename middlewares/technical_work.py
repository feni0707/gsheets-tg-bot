from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from logging import getLogger

from data.config import ADMINS_ID
from data.consts import TECHNICAL_WORK


logger = getLogger("tg_bot")


class TechnicalWorkMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        from handlers.user import redis

        if await redis.get_state_tech_work():
            print("ЖЕСТКИЕ ТЕХРАБОТЫ")
            msg = data["event_from_user"]
            if msg.id in ADMINS_ID:
                return await handler(event, data)
            else:
                logger.debug(
                    f"Пользователь {msg.first_name} с username: {msg.username} прислал апдейт с текстом: {getattr(event, 'text', '')}"
                )
                bot = event.bot
                if send_message := getattr(bot, "send_message", None):
                    await send_message(msg.id, TECHNICAL_WORK)
        else:
            return await handler(event, data)
