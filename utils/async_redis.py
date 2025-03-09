from aioredis import from_url
from datetime import datetime, timedelta


class AsyncRedis:
    def __init__(self):
        self._redis = from_url("redis://localhost")

    async def was_there_activity_today(
        self, user_id: int, any: bool = False, schedule: bool = False
    ):
        key = f"{user_id}_{'any' if any else 'schedule'}_activ_today"
        # now_date = date.today().strftime("%d-%m-%Y")
        current_datetime = datetime.now()
        current_date = current_datetime.date()
        current_time = current_datetime.time()
        midnight = timedelta(hours=0, minutes=0, seconds=0)
        now_time = timedelta(
            hours=current_time.hour,
            minutes=current_time.minute,
            seconds=current_time.second,
        )

        delta = midnight - now_time

        res = await self._redis.get(key)

        if not res:
            await self._redis.set(key, 1, ex=delta.seconds)
        return bool(res)

    async def get_id_schedule(self, key):
        return await self._redis.get(key)

    async def add_id_schedule(self, key, id):
        await self._redis.set(key, id, 172800)

    async def del_id_schedule(self, key):
        await self._redis.delete(key)

    async def get_state_tech_work(self):
        return int(await self._redis.get("state_technical_works"))

    async def set_state_tech_work(self, state):
        await self._redis.set("state_technical_works", int(state))
