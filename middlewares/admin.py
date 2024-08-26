from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from data.config import ADMIN_ID
from data.consts import TECHNICAL_WORK


class AdminMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        msg = data["event_from_user"]
        if msg.id == int(ADMIN_ID):
            return await handler(event, data)
        else:
            print(
                f"Пользователь {msg.first_name} с username: {msg.username} прислал апдейт с текстом {getattr(event, 'text', '')}"
            )
            bot = event.bot
            if send_message := getattr(bot, "send_message", None):
                await send_message(msg.id, TECHNICAL_WORK)
