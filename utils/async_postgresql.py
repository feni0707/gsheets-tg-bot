import asyncpg
import logging
from asyncpg import Connection
from asyncpg.pool import Pool
from datetime import date

from data.consts import PERSON_TYPE_TEXTS, CLASSES_BY_SHIFT
from data import config


class AsyncPostgreSQL:
    async def create_pool(self):
        pool = await asyncpg.create_pool(
            user=config.DB_USER,
            command_timeout=60,
            password=config.DB_PASSWORD,
            database=config.DB_DATABASE,
            host="127.0.0.1",
        )
        if isinstance(pool, Pool):
            self.pool: Pool = pool
        else:
            raise RuntimeError("Ошибка подключения к бд")

    async def add_user(
        self,
        *,
        user_id: int,
        nick_name: str | None = None,
        first_name: str | None,
        reg_date: str,
        last_action_date: str,
        person_type: str,
        school_class: str | None = None,
        profiles: str | None = None,
        recieve_notifications: bool,
    ):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                if not await self.user_exists(user_id):
                    request = "INSERT INTO users \
                    (user_id, nick_name, first_name, last_action_date, person_type, \
                    school_class, profiles, recieve_notifications, reg_date) \
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
                    type_notify = "Зарегистрирован"
                    variable_args = (reg_date,)
                else:
                    request = "UPDATE users \
                    SET nick_name=$2, first_name=$3, last_action_date=$4, \
                    person_type=$5, school_class=$6, profiles=$7, recieve_notifications=$8 \
                    WHERE user_id = $1"
                    type_notify = "Перерегистрирован"
                    variable_args = ()
                res = await conn.execute(
                    request,
                    user_id,
                    nick_name,
                    first_name,
                    last_action_date,
                    person_type,
                    school_class,
                    profiles,
                    recieve_notifications,
                    *variable_args,
                )
                logging.info(
                    f"{type_notify} {PERSON_TYPE_TEXTS[person_type].lower()} {first_name} {school_class}"
                )
                return res

    async def user_exists(self, user_id: int):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch(
                    "SELECT * FROM users WHERE user_id = $1", user_id
                )
                return bool(res)

    async def exist_daily_record(self):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                now_date = date.today().strftime("%d-%m-%Y")
                res = await conn.fetch(
                    "SELECT * FROM daily_statistics WHERE date_record = $1", now_date
                )
                return bool(res)

    async def add_daily_record(self):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                now_date = date.today().strftime("%d-%m-%Y")
                res = await conn.fetch(
                    "INSERT INTO daily_statistics (date_record, students_req, teachers_req, \
                    parents_req, uniq_students, uniq_teachers, uniq_parents, uniq_schedule_req) \
                    VALUES ($1, 0, 0, 0, 0, 0, 0, 0)",
                    now_date,
                )
                return res

    async def increment_daily_statistic(self, type_profile: str, is_uniq: bool = False):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                now_date = date.today().strftime("%d-%m-%Y")
                res = await conn.fetch(
                    f"UPDATE daily_statistics SET {type_profile}s_req={type_profile}s_req + 1, \
                    uniq_{type_profile}s=uniq_{type_profile}s + {int(is_uniq)} \
                    WHERE date_record=$1;",
                    now_date,
                )
                return res

    async def update_last_action_date(self, user_id: int):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                now_date = date.today().strftime("%d-%m-%Y")
                res = await conn.fetch(
                    "UPDATE users SET last_action_date=$2 WHERE user_id = $1",
                    user_id,
                    now_date,
                )
                return res

    async def increment_uniq_schedule_req(self):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                now_date = date.today().strftime("%d-%m-%Y")
                res = await conn.fetch(
                    f"UPDATE daily_statistics SET uniq_schedule_req = uniq_schedule_req + 1 \
                    WHERE date_record=$1;",
                    now_date,
                )
                return res

    async def get_person_type(self, user_id: int):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch(
                    "SELECT person_type FROM users WHERE user_id = $1", user_id
                )
                return res[0]["person_type"]

    async def get_notify_true_users_group_by_class(self, shift: int):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                if shift == 1:
                    request = "SELECT user_id, school_class FROM users WHERE \
                    recieve_notifications=True AND school_class IN ($1, $2, $3, $4, $5, $6, $7, \
                    $8, $9, $10, $11, $12, $13, $14, $15, $16, $17) \
                    GROUP BY user_id, school_class ORDER BY school_class"
                else:
                    request = "SELECT user_id, school_class FROM users WHERE \
                    recieve_notifications=True AND school_class IN ($1, $2, $3, $4, $5, $6, $7, \
                    $8, $9, $10, $11, $12) \
                    GROUP BY user_id, school_class ORDER BY school_class"
                res = await conn.fetch(request, *CLASSES_BY_SHIFT[shift])
                ans = {}
                for record in res:
                    key = record["school_class"][:2]
                    value = record["user_id"]
                    if ans.get(key, "list_not_exists") == "list_not_exists":
                        ans[key] = [value]
                    else:
                        ans[key].append(value)
                return ans

    async def get_notify_true_teachers(self):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch(
                    "select user_id from users where users.person_type = 'teacher'"
                )
                return [rec[0] for rec in res]

    async def increment_school_claseses(self):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch(
                    f"SELECT id, school_class FROM users WHERE school_class SIMILAR TO '[5-8]%|10%'"
                )
                for record in res:
                    last_sc = record["school_class"]
                    id = record["id"]
                    new_sc = f"{int(last_sc[:-1]) + 1}{last_sc[-1]}"
                    await self.__update_school_class(id, new_sc)

    async def turn_off_notify_9_and_11_classes(self):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch(
                    "UPDATE users SET recieve_notifications = false WHERE school_class SIMILAR TO '9%|11%'"
                )
                return res

    async def __update_school_class(self, id: int, school_class: str):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch(
                    "UPDATE users SET school_class=$2 WHERE id = $1", id, school_class
                )
                return res

    async def get_one_raz_users(self):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch(
                    "select user_id from users where school_class similar to '9%'"
                )
                return [rec[0] for rec in res]

    async def get_all_users(self):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch("select user_id from users")
                return [rec[0] for rec in res]

    async def set_recieve_notifications(self, user_id, recieve_notifications):
        async with self.pool.acquire() as conn:
            conn: Connection
            async with conn.transaction():
                res = await conn.fetch(
                    "UPDATE users SET recieve_notifications=$2 WHERE user_id=$1",
                    user_id,
                    recieve_notifications,
                )
                return res
