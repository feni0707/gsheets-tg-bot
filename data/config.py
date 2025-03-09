from environs import Env

env = Env()
env.read_env(".env")

BOT_TOKEN: str = env.str("BOT_TOKEN")
ADMIN_ID: int = env.str("ADMIN_ID")
ADMINS_ID = list(map(int, env.str("ADMINS_ID").replace(" ", "").split(",")))

DB_USER: str = env.str("DB_USER")
DB_PASSWORD: str = env.str("DB_PASSWORD")
DB_DATABASE: str = env.str("DB_DATABASE")
