# data/config.py
from environs import Env

env = Env()
env.read_env()

# Bot sozlamalari
BOT_TOKEN = env.str("BOT_TOKEN")
ADMINS = env.list("ADMINS", subcast=int)
IP = env.str("IP", "localhost")

# Django API
API_BASE_URL = env.str("API_BASE_URL", "https://sebmarket.uz/api/payments")

# Database
DB_PATH = env.str("DB_PATH", "data/phones.db")

# Boshqa
START_PHOTO_FILE_ID = "AgACAgIAAxkBAAIbHWk4P8fZt-Ir3804yO8XHmusmDw7AAJyEWsbigTBScr0wXcXOjb8AQADAgADeAADNgQ"