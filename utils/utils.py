from string import Template
from typing import Any, Dict, List
from aiogram import Bot
from datetime import datetime

from aiogram.types import Message
from data.consts import SCHOOL_DAYS
from utils.async_redis import AsyncRedis
import logging

redis = AsyncRedis()


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
                    logging.error(f"{schedule}\n{school_class}\n{day}")
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
            else:
                continue
            day_edited_schedule = (
                "сегодня" if index_now_day == SCHOOL_DAYS.index(day) else "завтра"
            )
            data = (text, day_edited_schedule)
            if data not in days_notify:
                days_notify.append(data)

            await redis.del_id_schedule(f"{day}:{school_class.upper()}")
            for user_id in list_user_id:
                add_text = f"{shift} смены" if user_id in teachers else ""
                try:
                    await bot.send_message(
                        user_id,
                        f"🔔{text} расписание {add_text} на {day_edited_schedule}",
                    )
                    count_notify_users += 1
                except:
                    pass

    if days_notify:
        for teacher_id in teachers:
            flag = False
            for text, day_edited_schedule in days_notify:
                try:
                    await bot.send_message(
                        teacher_id,
                        f"🔔{text} расписание {shift} смены на {day_edited_schedule}",
                    )
                    flag = True
                except:
                    pass

            if not flag:
                continue
            count_notify_users += 1

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
            logging.error(f"Ошибка при удалении файла {file_path}. {e}")


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
