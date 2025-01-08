from typing import Dict, List
import gspread_asyncio
from string import ascii_uppercase
from google.oauth2.service_account import Credentials
from json import dumps, loads
from asyncio import sleep
import logging
import aioredis

from data.consts import FIRST_SHIFT_CLASSES, SCHOOL_DAYS, SECOND_SHIFT_CLASSES
from pillow.img_creator import ImgSchedule
from utils.utils import send_notify_to_users
from handlers.user import db


class GoogleTable:
    def __init__(
        self,
        credence_service_file: str,
        googlesheet_file_key: str,
        school_shift: int,
    ) -> None:
        self.credence_service_file = credence_service_file
        self.googlesheet_file_key = googlesheet_file_key
        self.school_shift = school_shift

    def __get_creds(self):
        creds = Credentials.from_service_account_file(self.credence_service_file)
        scoped = creds.with_scopes(
            [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
        )
        return scoped

    async def __get_table(self):
        agcm = gspread_asyncio.AsyncioGspreadClientManager(self.__get_creds)
        agc = await agcm.authorize()
        ss = await agc.open_by_key(self.googlesheet_file_key)
        table = await ss.get_sheet1()
        self.__table: gspread_asyncio.AsyncioGspreadWorksheet = table

    async def __set_consts(self):
        self.__col_to_end = 56 if self.school_shift == 1 else 61
        self.__len_day = 8 if self.school_shift == 1 else 9
        if self.school_shift == 1:
            first_class = "5 а"
            last_class = "11 б"
            classes = FIRST_SHIFT_CLASSES
        else:
            first_class = "6 а"
            last_class = "10 б"
            classes = SECOND_SHIFT_CLASSES

        self.__first_class, self.__last_class, self.__classes = (
            first_class,
            last_class,
            classes,
        )

    async def __set_ranges(self):
        start, end = [
            (await self.__table.find(data)).address
            for data in (self.__first_class, self.__last_class)
        ]
        end = f"{end[0]}{int(end[1]) + self.__col_to_end}"
        self.__start, self.__end = start, end
        self.__index_end_col = ascii_uppercase.index(self.__end[0])
        self.__right_col = ascii_uppercase[self.__index_end_col + 1]
        self.__start_high_school_col = ascii_uppercase[self.__index_end_col - 1]
        self.__start_row = int(self.__start[1])

    async def __fill_right_col(self):
        await self.__table.add_cols(1)
        self.__range_rigth_col = f"{self.__right_col}{self.__start_row}:{self.__right_col}{self.__start_row + self.__col_to_end}"
        await self.__table.update(
            [["1"] for _ in range(self.__col_to_end)], self.__range_rigth_col
        )

    async def __clear_right_col(self):
        # await self.__table.batch_clear([self.__range_rigth_col])
        await self.__table.delete_columns(self.__index_end_col + 2)

    async def __get_list_merjed_cells(self):
        range_cells = f"{self.__start_high_school_col}{self.__start_row}:{self.__right_col}{self.__end[1:]}"
        values_with_combine = await self.__table.get(
            range_name=range_cells,
            combine_merged_cells=True,
        )
        values_no_combine = await self.__table.get(range_cells)
        self.__list_merjed_cells = [
            (
                list_combine_values[0]
                if len(set(list_combine_values)) == 2
                and len(set(list_no_combine_values)) == 3
                else ""
            )
            for list_combine_values, list_no_combine_values in zip(
                values_with_combine, values_no_combine
            )
        ]

    async def __rename_high_classes_to_one_class(self):
        index = self.__classes[-1][:-1]
        self.__school_schedule[index] = {}
        for day in SCHOOL_DAYS:
            self.__school_schedule[index][day] = {}
            for school_class in self.__classes[-2:]:
                self.__school_schedule[index][day][school_class] = (
                    self.__school_schedule[school_class][day]
                )

        for key in self.__classes[-2:]:
            del self.__school_schedule[key]

    async def __get_schedule(self):
        await self.__set_consts()
        await self.__set_ranges()
        table_values = await self.__table.get(
            f"{self.__start}:{self.__end}", major_dimension="columns"
        )
        await self.__fill_right_col()
        await self.__get_list_merjed_cells()
        await self.__clear_right_col()

        self.__school_schedule = {}
        self.__merged_cells: Dict[str, List[str]] = {}
        for index, school_class in enumerate(self.__classes):
            self.__school_schedule[school_class] = {}
            for index_day, day in enumerate(SCHOOL_DAYS):
                start = self.__start_row + index_day * (self.__len_day + 1) - 1
                end = start + self.__len_day + (day == SCHOOL_DAYS[-1])
                self.__school_schedule[school_class][day] = table_values[index][
                    start:end
                ]
                self.__merged_cells[day] = self.__list_merjed_cells[start:end]
                # if day == SCHOOL_DAYS[-1]:
                #     self.__school_schedule[school_class][day].insert(0, "")

        await self.__rename_high_classes_to_one_class()

    async def __is_table_update(self, in_while: bool = False):
        await self.__get_schedule()
        key = f"{self.school_shift}_shift_last_schedule"
        last_schedule = await self.__redis.get(key)
        if not in_while:
            self._last_schedule = loads(last_schedule) if last_schedule else None
        if not last_schedule or not (self.__school_schedule == loads(last_schedule)):
            await self.__redis.set(key, dumps(self.__school_schedule))
            logging.info(f"Расписание {self.school_shift} смены добавлено в кеш")
            return True
        return False

    async def __is_table_finaly_edited(self):
        if await self.__is_table_update():
            n = 3
            while n:
                await sleep(100)
                if await self.__is_table_update(in_while=True):
                    n = 3
                else:
                    n -= 1
            return True

    async def start_polling(self):
        self.__redis = aioredis.from_url("redis://localhost")
        await self.__get_table()
        logging.info(f"start_polling schedule {self.school_shift} shift")
        while True:
            logging.info(f"Поллинг расписания {self.school_shift} смены")
            if not (await self.__is_table_finaly_edited()):
                continue
            from bot import bot

            logging.info(f"Расписание {self.school_shift} смены изменено")
            img = ImgSchedule(self.school_shift)
            # last_schedule = await self.__redis.get(
            #     f"{self.school_shift}_shift_last_schedule"
            # )
            data_users = await db.get_notify_true_users_group_by_class(
                self.school_shift
            )
            await img.schedule_to_pictures(self.__school_schedule, self.__merged_cells)
            count_notify_users = await send_notify_to_users(
                bot, self._last_schedule, self.__school_schedule, data_users
            )
            if count_notify_users:
                text = f"Уведомления разосланы {count_notify_users} пользователям"
            else:
                text = "Уведомления рассылать некому"
            logging.info(f"{self.school_shift} смена | {text}")
            await sleep(300)
