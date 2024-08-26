from environs import Env

env = Env()
env.read_env()

BOT_TOKEN: str = env.str("BOT_TOKEN")
ADMIN_ID: int = env.str("ADMIN_ID")
