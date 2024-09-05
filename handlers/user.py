from contextlib import suppress
from aiogram import F, Router, Bot
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove, FSInputFile
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from re import match
from datetime import datetime
import logging
import asyncio
from time import time
from os.path import isfile as is_file_exists

from dotmap import pprint

from keyboards.keyboards import get_choose_profile_keyboard, get_settings_kb, keyboards
from states.user import User_States
from data import consts
from utils.utils import get_profile_info, send_notify_to_users
from utils.async_postgresql import AsyncPostgreSQL
from utils.async_redis import AsyncRedis

# from bot import bot

router = Router()
db = AsyncPostgreSQL()
redis = AsyncRedis()
loop = asyncio.get_event_loop()
loop.run_until_complete(db.create_pool())


@router.message(CommandStart())
async def start(msg: Message, state: FSMContext):
    if await state.get_state():
        await msg.answer(consts.START_QUESTION, reply_markup=keyboards.menu_or_reset)
        await state.set_state(User_States.menu_or_reset)
    else:
        await msg.answer(
            consts.TEMPLATE_START.substitute(user=msg.chat.full_name),
            reply_markup=keyboards.start_menu,
        )
        await state.set_data({})
        await state.set_state(User_States.start_menu)


@router.message(Command("menu"))
async def get_menu(msg: Message, state: FSMContext):
    if "recieve_notifications" in await state.get_data():
        await msg.answer(
            consts.TEXT_FOR_KB["menu_or_reset"][1], reply_markup=keyboards.menu
        )
        await state.set_state(User_States.menu)
    else:
        await msg.answer(consts.NOT_REGISTR)


@router.message(User_States.menu_or_reset)
async def menu_or_reset(msg: Message, state: FSMContext):
    if msg.text in consts.TEXT_FOR_KB["menu_or_reset"]:
        if msg.text == consts.TEXT_FOR_KB["menu_or_reset"][0]:
            await state.set_state(None)
            await start(msg, state)
        else:
            await get_menu(msg, state)
    else:
        await not_understend(msg)


@router.message(User_States.start_menu)
async def start_menu(msg: Message, state: FSMContext):
    if msg.text in consts.TEXT_FOR_KB["start_menu"]:
        if msg.text != "👩🏻‍🏫Учитель":
            person_type = "student" if msg.text == "🎓Ученик" else "parent"
            text = consts.CHOOSE_CLASS_DICT[person_type]
            new_state = User_States.choose_class
            keyboard = ReplyKeyboardRemove()
            await state.update_data(person_type=person_type)
            await state.set_state(new_state)
            await msg.answer(text=text, reply_markup=keyboard)
        else:
            # text = consts.REGISTR_SUCCESSFUL
            text = "Регистрация для учителей пока, что недоступна"
            person_type = "teacher"
            new_state = User_States.menu
            keyboard = keyboards.menu
            # await state.update_data(recieve_notifications=False)
            await msg.answer(text)
    else:
        await not_understend(msg)


@router.message(User_States.choose_class)
async def choose_class(msg: Message, state: FSMContext):
    text = msg.text.replace(" ", "") if isinstance(msg.text, str) else ""
    if text and len(text) in [2, 3]:
        for pattern in [r"[5-9][а-дА-Д]", r"1[0-1][а-бА-Б]"]:
            if match(pattern, text):
                await state.update_data(school_class=text.upper())
                # if len(text) == 3:
                #     await msg.answer(
                #         consts.CHOOSE_PROFILE,
                #         reply_markup=(await get_choose_profile_keyboard())[0],
                #     )
                #     await state.set_state(User_States.choose_profiles)
                #     await state.update_data(profiles=[])
                # else:
                await msg.answer(
                    consts.YES_NO_NOTIFY,
                    reply_markup=keyboards.yes_no,
                )
                await state.set_state(User_States.yes_no_notify)
                return

    data = await state.get_data()
    await msg.answer(
        consts.CHOOSE_CLASS_TRY_AGAIN + consts.CHOOSE_CLASS_DICT[data["person_type"]]
    )


@router.callback_query(User_States.choose_profiles, F.data)
async def choose_profiles(call: CallbackQuery, state: FSMContext):
    if isinstance(call.message, Message):
        profiles = (await state.get_data())["profiles"]
        if call.data == "done":
            if len(profiles) < 2:
                await call.answer(consts.CHOOSE_PROFILE, show_alert=True)
            else:
                # await call.message.delete()
                await call.message.answer(
                    consts.YES_NO_NOTIFY,
                    reply_markup=keyboards.yes_no,
                )
                await state.set_state(User_States.yes_no_notify)
        else:
            keyboard, pressed_buttons = await get_choose_profile_keyboard(
                profiles, call.data
            )
            with suppress(TelegramBadRequest):
                await call.message.edit_reply_markup(reply_markup=keyboard)
                await state.update_data(profiles=pressed_buttons)


@router.message(User_States.yes_no_notify)
async def yes_no_notify(msg: Message, state: FSMContext):
    if msg.text in consts.TEXT_FOR_KB["yes_no"]:
        ans = msg.text == "✅Да"
    else:
        await not_understend(msg)
        return
    data = await state.get_data()
    date = msg.date.strftime("%d-%m-%Y")
    profiles = data.get("profiles", None)
    await db.add_user(
        user_id=msg.chat.id,
        nick_name=msg.chat.username,
        first_name=msg.chat.first_name,
        reg_date=date,
        last_action_date=date,
        person_type=data.get("person_type", None),
        school_class=data.get("school_class", "") + data.get("letter", "").upper(),
        profiles=", ".join(profiles) if profiles else None,
        recieve_notifications=ans,
    )

    await state.update_data(recieve_notifications=ans)
    await msg.answer(consts.REGISTR_SUCCESSFUL, reply_markup=keyboards.menu)
    await state.set_state(User_States.menu)


@router.message(User_States.menu)
async def menu(msg: Message, state: FSMContext):
    if msg.text in consts.TEXT_FOR_KB["menu"]:
        await db.increment_school_claseses()
        if msg.text == "👤Профиль":
            data = await state.get_data()
            text = await get_profile_info(
                data["person_type"], data.get("school_class", "")
            )
            await msg.answer(
                text.substitute(
                    person_type=consts.PERSON_TYPE_TEXTS[data["person_type"]],
                    school_class=data.get("school_class", "")
                    + data.get("letter", "").upper(),
                    profiles=", ".join(
                        consts.DICT_PROFILES[profile]
                        for profile in data.get("profiles", [])
                    ),
                    status_of_notify=(
                        "Включены" if data["recieve_notifications"] else "Отключены"
                    ),
                ),
                parse_mode="Markdown",
            )
        else:
            if msg.text == "🗓Расписаниe":
                new_state = "schedule"
                keyboard = keyboards.schedule
            else:
                new_state = "settings"
                keyboard = await get_settings_kb(
                    (await state.get_data())["recieve_notifications"]
                )
            await msg.answer(msg.text, reply_markup=keyboard)
            await state.set_state(getattr(User_States, new_state))

        if not await db.user_exists(msg.chat.id):
            data = await state.get_data()
            date = msg.date.strftime("%d-%m-%Y")
            profiles = data.get("profiles", None)
            await db.add_user(
                user_id=msg.chat.id,
                nick_name=msg.chat.username,
                first_name=msg.chat.first_name,
                reg_date=date,
                last_action_date=date,
                person_type=data.get("person_type", None),
                school_class=data.get("school_class", "")
                + data.get("letter", "").upper(),
                profiles=", ".join(profiles) if profiles else None,
                recieve_notifications=data.get("recieve_notifications", False),
            )
    else:
        await not_understend(msg)
        return


@router.message(User_States.schedule)
async def schedule(msg: Message, state: FSMContext):
    if msg.text not in consts.TEXT_FOR_KB["schedule"]:
        await not_understend(msg)
        return
    if msg.text == "🔙Назад":
        await msg.answer(msg.text, reply_markup=keyboards.menu)
        await state.set_state(User_States.menu)
        return
    if not await redis.was_there_activity_today(msg.chat.id, schedule=True):
        await db.increment_uniq_schedule_req()
    data = await state.get_data()
    if data["person_type"] != "teacher":
        # weekday = datetime.today().weekday()
        index_now_weekday = datetime.today().weekday() + (
            msg.text == consts.TEXT_FOR_KB["schedule"][-1]
        )
        if index_now_weekday == 6:
            await msg.answer("Уроков нету😃")
            return
        weekdays = consts.SCHOOL_DAYS * 2
        now_weekday = weekdays[index_now_weekday]
        if data.get("letter", ""):
            school_class = data["school_class"] + (
                data["letter"] if len(data["school_class"]) == 1 else ""
            )
        else:
            school_class = data["school_class"][:2]
        try:
            key = f"{now_weekday}:{school_class.upper()}"
            path = f"pillow/images/schedules/{now_weekday}/{school_class.upper()}.jpg"
            if not is_file_exists(path):
                await msg.answer("Расписание ещё не известно")
                return
            photo = await redis.get_id_schedule(key)
            id_photo_exists = bool(photo)
            if not id_photo_exists:
                photo = FSInputFile(
                    f"pillow/images/schedules/{now_weekday}/{school_class.upper()}.jpg"
                )
            msg_sended_photo = await msg.answer_photo(photo)
            if not id_photo_exists and msg_sended_photo.photo:
                photo_id = msg_sended_photo.photo[-1].file_id
                await redis.add_id_schedule(key, photo_id)
        except:
            logging.error(
                f"Нет такого файла info: @{msg.chat.username} {msg.chat.first_name} {school_class}"
            )
            await msg.answer("Ошибка")
    else:
        await msg.answer(msg.text)

    if not await db.user_exists(msg.chat.id):
        data = await state.get_data()
        date = msg.date.strftime("%d-%m-%Y")
        profiles = data.get("profiles", None)
        await db.add_user(
            user_id=msg.chat.id,
            nick_name=msg.chat.username,
            first_name=msg.chat.first_name,
            reg_date=date,
            last_action_date=date,
            person_type=data.get("person_type", None),
            school_class=data.get("school_class", "") + data.get("letter", "").upper(),
            profiles=", ".join(profiles) if profiles else None,
            recieve_notifications=data.get("recieve_notifications", False),
        )


@router.message(User_States.settings)
async def settings(msg: Message, state: FSMContext):
    buttons = consts.TEXT_FOR_KB["settings"]
    if msg.text in buttons:
        if msg.text == buttons[0]:
            await msg.answer(consts.CONFIRMATION_RESET, reply_markup=keyboards.yes_no)
            await state.set_state(User_States.confimation_reset_settings)
        elif msg.text in buttons[2:]:
            notify = (await state.get_data())["recieve_notifications"]
            await msg.answer(
                consts.TEMPLATE_RESET_NOTFY.substitute(
                    state_notify="включены" if not notify else "отключены"
                ),
                reply_markup=await get_settings_kb(not notify),
            )
            await state.update_data(recieve_notifications=not notify)
        else:
            await msg.answer(msg.text, reply_markup=keyboards.menu)
            await state.set_state(User_States.menu)
    else:
        await not_understend(msg)


@router.message(User_States.confimation_reset_settings)
async def confimation_reset_settings(msg: Message, state: FSMContext):
    buttons = consts.TEXT_FOR_KB["yes_no"]
    if msg.text in buttons:
        if msg.text == buttons[0]:
            await state.set_state(None)
            await start(msg, state)
        else:
            await msg.answer(
                consts.CANCEL_RESET,
                reply_markup=await get_settings_kb(
                    (await state.get_data())["recieve_notifications"]
                ),
            )
            await state.set_state(User_States.settings)
    else:
        await not_understend(msg)


@router.message()
async def not_understend(msg: Message):
    logging.info(
        f"Пользователь @{msg.chat.username} {msg.chat.full_name} написал: {msg.text}"
    )
    await msg.answer("Я тебя не понял")
