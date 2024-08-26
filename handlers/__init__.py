from aiogram import Router
from aiogram.filters import CommandStart, StateFilter

from filters import ChatTypeFilter


def prepare_router() -> Router:
    user_router = Router()
    user_router.message.filter(ChatTypeFilter('private'))

    return user_router

