from string import Template
from typing import Any, Dict, List
from aiogram import Bot
from datetime import datetime
from logging import getLogger
from logging.handlers import TimedRotatingFileHandler

from aiogram.types import Message
from data.consts import SCHOOL_DAYS
from utils.async_redis import AsyncRedis
import logging

redis = AsyncRedis()
logger = getLogger("tg_bot")


async def get_profile_info(person_type: str):
    answer = "👤*Тип аккаунта*: $person_type\n🔔*Уведомления*: $status_of_notify"
    if person_type != "teacher":
        answer += "\n🏫*Класс*: $school_class"
        # if int(school_class) > 9:
        #     answer += "\n📚*Профильные предметы*: $profiles"

    return Template(answer)


async def send_notify_to_users(
    bot: Bot,
    shift,
    last_school_schedule,
    new_school_schedule,
    users_by_class: Dict[str, List[int]],
    teachers,
):
    schedules = {"last": last_school_schedule, "new": new_school_schedule}
    count_notify_users = 0
    days_notify = []
    notifications = {
        "сегодня": {"Появилось": set(), "Изменилось": set()},
        "завтра": {"Появилось": set(), "Изменилось": set()},
    }
    blocks = 0
    deactivate = 0
    another = 0

    b = "Telegram server says - Forbidden: bot was blocked by the user"
    d = "Telegram server says - Forbidden: user is deactivated"
    nf = "Telegram server says - Bad Request: chat not found"

    for school_class, list_user_id in users_by_class.items():
        index_now_day = datetime.today().weekday()
        days = SCHOOL_DAYS * 2
        for day in days[index_now_day : index_now_day + 2]:
            if day == 6:
                continue
            current_schedules = {}
            for time, schedule in schedules.items():
                try:
                    current_schedules[time] = schedule[school_class][day]
                except:
                    logger.error(f"{schedule}\n{school_class}\n{day}")
                if school_class.isdigit():
                    current_schedules[time] = [
                        item for lst in current_schedules[time].values() for item in lst
                    ]
            if not list(filter(bool, current_schedules["new"])):
                continue
            elif not list(filter(bool, current_schedules["last"])):
                text = "Появилось"
            elif current_schedules["last"] != current_schedules["new"]:
                text = "Изменилось"
                logger.info(
                    f'Старое: {current_schedules["last"]}, новое: {current_schedules["new"]}'
                )
            else:
                continue
            day_edited_schedule = (
                "сегодня" if index_now_day == SCHOOL_DAYS.index(day) else "завтра"
            )
            data = (text, day_edited_schedule)
            if data not in days_notify:
                days_notify.append(data)

            notifications[day_edited_schedule][text].add(school_class)

            await redis.del_id_schedule(f"{day}:{school_class.upper()}")
            for user_id in list_user_id:
                add_text = f"{shift} смены" if user_id in teachers else ""
                try:
                    await bot.send_message(
                        user_id,
                        f"🔔{text} расписание {add_text} на {day_edited_schedule}",
                    )
                    count_notify_users += 1
                except Exception as e:
                    if str(e) == b:
                        blocks += 1
                    elif str(e) == d:
                        deactivate += 1
                    elif str(e) == nf:
                        pass
                    else:
                        another += 1
                        logger.error(f"Ошибка отправки уведомления {user_id} {e}")

    logger.info(f"{notifications}")

    if days_notify:
        for teacher_id in teachers:
            flag = False
            r = ""
            for text, day_edited_schedule in days_notify:
                try:
                    await bot.send_message(
                        teacher_id,
                        f"🔔{text} расписание {shift} смены на {day_edited_schedule}",
                    )
                    flag = True
                except Exception as e:
                    # logger.error(
                    #     f"Ошибка отправки уведомления учителю {teacher_id} {e}"
                    # )
                    r = str(e)

            if not flag:
                if r == b:
                    blocks += 1
                elif r == d:
                    deactivate += 1
                else:
                    another += 1
                    logger.error(f"Ошибка отправки уведомления {teacher_id} {r}")
                continue
            count_notify_users += 1

    logger.info(
        f"В {shift} смене заблокировано {blocks}, деактивировано {deactivate}, по другим причинам {another}"
    )

    return count_notify_users


import os


def delete_last_day_photos():
    index_now_weekday = datetime.today().weekday()
    weekday = SCHOOL_DAYS[index_now_weekday - 1]
    folder_path = f"pillow/images/schedules/{weekday}/"
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"Ошибка при удалении файла {file_path}. {e}")


def delete_photo(school_class, day):
    photo_path = f"pillow/images/schedules/{day}/{school_class}"
    try:
        if os.path.exists(photo_path):
            os.remove(photo_path)
    except Exception as e:
        print(f"{e} | {day}/{school_class}")


def get_user_args(msg: Message, data: Dict[str, Any]) -> Dict[str, Any]:
    date = msg.date.strftime("%d-%m-%Y")
    profiles = data.get("profiles", None)
    args = {
        "user_id": msg.chat.id,
        "nick_name": msg.chat.username,
        "first_name": msg.chat.first_name,
        "reg_date": date,
        "last_action_date": date,
        "person_type": data.get("person_type", None),
        "school_class": data.get("school_class", "") + data.get("letter", "").upper(),
        "profiles": ", ".join(profiles) if profiles else None,
        "recieve_notifications": data.get("recieve_notifications", False),
    }

    return args


def setup_logger():
    logger = logging.getLogger("tg_bot")

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        handler = TimedRotatingFileHandler(
            "logs/tg_bot.log", when="midnight", interval=1, backupCount=30
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - [%(levelname)s] - %(name)s - (%(filename)s).%(funcName)s(%(lineno)d) - %(message)s",
            )
        )

        logger.addHandler(handler)

        aiogram_logger = logging.getLogger("aiogram")
        aiogram_logger.setLevel(logging.INFO)
        aiogram_logger.addHandler(handler)

    return logger
