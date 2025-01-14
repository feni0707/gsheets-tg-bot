from aiogram import Router
from aiogram.types import Message, FSInputFile, ReplyKeyboardRemove
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from re import fullmatch
from datetime import datetime
import logging
import asyncio
from os.path import isfile as is_file_exists

from keyboards.keyboards import get_settings_kb, keyboards
from states.user import User_States
from data import consts
from utils.utils import get_profile_info, get_user_args
from utils.async_postgresql import AsyncPostgreSQL
from utils.async_redis import AsyncRedis

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
        await not_understend(msg, state)


@router.message(User_States.start_menu)
async def start_menu(msg: Message, state: FSMContext):
    if isinstance(msg.text, str) and msg.text in consts.TEXT_FOR_KB["start_menu"]:
        person_type = consts.PERSON_TYPE_FOR_DB[msg.text]
        text = consts.START_MENU_TEXT[person_type]
        new_state = consts.START_MENU_STATE[msg.text]
        if person_type != "teacher":
            keyboard = ReplyKeyboardRemove()
        else:
            keyboard = keyboards.yes_no
        await state.update_data(person_type=person_type)
        await state.set_state(new_state)
        await msg.answer(text=text, reply_markup=keyboard)
    else:
        await not_understend(msg, state)


@router.message(User_States.choose_class)
async def choose_class(msg: Message, state: FSMContext):
    text = msg.text.replace(" ", "") if isinstance(msg.text, str) else ""
    if text and len(text) in [2, 3]:
        for pattern in [r"[5-9][а-дА-Д]", r"1[0-1][а-бА-Б]"]:
            if fullmatch(pattern, text):
                await state.update_data(school_class=text.upper())
                await msg.answer(
                    consts.YES_NO_NOTIFY,
                    reply_markup=keyboards.yes_no,
                )
                await state.set_state(User_States.yes_no_notify)
                return
        if fullmatch(r"[1-4][а-дА-Д]", text):
            await msg.answer(consts.BOT_NOT_FOR_JUNS)
            return

    data = await state.get_data()
    await msg.answer(
        consts.CHOOSE_CLASS_TRY_AGAIN + consts.CHOOSE_CLASS_DICT[data["person_type"]]
    )


@router.message(User_States.yes_no_notify)
async def yes_no_notify(msg: Message, state: FSMContext):
    if msg.text in consts.TEXT_FOR_KB["yes_no"]:
        ans = msg.text == consts.TEXT_FOR_KB["yes_no"][-1]
    else:
        await not_understend(msg, state)
        return
    data = await state.get_data()
    await db.add_user(**get_user_args(msg, data))

    await state.update_data(recieve_notifications=ans)
    await msg.answer(consts.REGISTR_SUCCESSFUL, reply_markup=keyboards.menu)
    await state.set_state(User_States.menu)


@router.message(User_States.menu)
async def menu(msg: Message, state: FSMContext):
    if msg.text not in consts.TEXT_FOR_KB["menu"]:
        await not_understend(msg, state)
        return
    data = await state.get_data()
    if msg.text == consts.TEXT_FOR_KB["menu"][0]:
        text = await get_profile_info(data["person_type"])
        await msg.answer(
            text.substitute(
                person_type=consts.PERSON_TYPE_TEXTS[data["person_type"]],
                school_class=data.get("school_class", "")
                + data.get("letter", "").upper(),
                # profiles=", ".join(
                #     consts.DICT_PROFILES[profile]
                #     for profile in data.get("profiles", [])
                # ),
                status_of_notify=(
                    "Включены" if data["recieve_notifications"] else "Отключены"
                ),
            ),
            parse_mode="Markdown",
        )
    else:
        if msg.text == consts.TEXT_FOR_KB["menu"][-1]:
            new_state = "schedule"
            keyboard = keyboards.get(f'{data["person_type"]}_schedule')
        else:
            new_state = "settings"
            keyboard = await get_settings_kb(
                (await state.get_data())["recieve_notifications"]
            )
        await msg.answer(msg.text, reply_markup=keyboard)
        await state.set_state(getattr(User_States, new_state))

    if not await db.user_exists(msg.chat.id):
        await db.add_user(**get_user_args(msg, data))


@router.message(User_States.schedule)
async def schedule(msg: Message, state: FSMContext):
    if msg.text not in consts.TEXT_FOR_KB["all_schedule"]:
        await not_understend(msg, state)
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
        weekdays = consts.DAYS * 2
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
        except Exception as e:
            logging.error(
                f"Ошибка отправки расписания info: @{msg.chat.username} {msg.chat.first_name} {school_class}\n{e}"
            )
            await msg.answer("Ошибка")
    else:
        if msg.text == consts.TEXT_FOR_KB["teacher_schedule"][-1]:
            text = f"<a href='https://docs.google.com/spreadsheets/d/1ukiRpvVSzrazcaRLrDzFOEGurAMOdj2_hpaOksSAy-k/edit?usp=sharing'>Расписание 1 смены доступно по ссылке</a>"
        else:
            text = f"<a href='https://docs.google.com/spreadsheets/d/1HTUYHHvPxBLZyUbcl2RCLCqn_WXJfCmTL8HaC7AFNQA/edit?usp=sharing'>Расписание 2 смены доступно по ссылке</a>"
        await msg.answer(text, parse_mode="HTML")

    if not await db.user_exists(msg.chat.id):
        data = await state.get_data()
        await db.add_user(**get_user_args(msg, data))


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
        await not_understend(msg, state)


@router.message(User_States.confimation_reset_settings)
async def confimation_reset_settings(msg: Message, state: FSMContext):
    buttons = consts.TEXT_FOR_KB["yes_no"]
    if msg.text in buttons:
        if msg.text == buttons[-1]:
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
        await not_understend(msg, state)


@router.message()
async def not_understend(msg: Message, state: FSMContext):
    state_user = await state.get_state()
    state_user = state_user[12:] if state_user else ""
    logging.info(
        f"Пользователь {msg.chat.full_name} (@{msg.chat.username}, state: {state_user}) написал: {msg.text}"
    )
    arg = {}
    if state_user:
        if state_user not in ("schedule", "settings"):
            arg["reply_markup"] = keyboards[state_user]
        elif state_user == "schedule":
            data = await state.get_data()
            arg["reply_markup"] = keyboards.get(f"{data['person_type']}_schedule")
        else:
            recieve_notifications = (await state.get_data())["recieve_notifications"]
            arg["reply_markup"] = await get_settings_kb(recieve_notifications)

    await msg.answer("Я вас не понял", **arg)
    if state_user in ("start_menu", "yes_no_notify"):
        texts = {
            "start_menu": consts.TEMPLATE_START.substitute(user=msg.chat.full_name),
            "yes_no_notify": consts.YES_NO_NOTIFY,
        }
        await msg.answer(texts[state_user])
