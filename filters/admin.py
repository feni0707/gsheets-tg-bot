from aiogram.filters import BaseFilter
from aiogram.types import Message

from data.config import ADMINS_ID


class IsAdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.id in ADMINS_ID
