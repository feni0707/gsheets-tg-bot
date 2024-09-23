from pprint import pprint
from string import Template
from typing import Dict, List
from aiogram import Bot
from datetime import datetime
from data.consts import SCHOOL_DAYS
from utils.async_redis import AsyncRedis
import logging

redis = AsyncRedis()


async def get_profile_info(person_type: str, school_class: str):
    answer = "👤*Тип аккаунта*: $person_type\n🔔*Уведомления*: $status_of_notify"
    if person_type != "teacher":
        answer += "\n🏫*Класс*: $school_class"
        # if int(school_class) > 9:
        #     answer += "\n📚*Профильные предметы*: $profiles"

    return Template(answer)


async def send_notify_to_users(
    bot: Bot,
    last_school_schedule,
    new_school_schedule,
    users_by_class: Dict[str, List[int]],
):
    schedules = {"last": last_school_schedule, "new": new_school_schedule}
    count_notify_users = 0

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
                    logging.error(f"{schedule}\n{schedule[school_class]}\n{day}")
                if school_class.isdigit():
                    current_schedules[time] = [
                        item for lst in current_schedules[time].values() for item in lst
                    ]
                # current_schedules[time] = list(filter(bool, current_schedules[time]))
            # print(current_schedules)
            if not list(filter(bool, current_schedules["new"])):
                # print(school_class, day, "нету расписания")
                continue
            elif not list(filter(bool, current_schedules["last"])):
                text = "Появилось"
                # print(school_class, day, "расписание появилось")
            elif current_schedules["last"] != current_schedules["new"]:
                text = "Изменилось"
                # print(school_class, day, "расписание изменилось")
            else:
                # print(school_class, day, "расписание не изменилось")
                continue
            day_edited_schedule = (
                "сегодня" if index_now_day == SCHOOL_DAYS.index(day) else "завтра"
            )
            await redis.del_id_schedule(f"{day}:{school_class.upper()}")
            for user_id in list_user_id:
                try:
                    await bot.send_message(
                        user_id, f"🔔{text} расписание на {day_edited_schedule}"
                    )
                    count_notify_users += 1
                except:
                    pass

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
