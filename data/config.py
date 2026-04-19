# data/config.py
from environs import Env

env = Env()
env.read_env()

# Bot sozlamalari
BOT_TOKEN = env.str("BOT_TOKEN")
ADMINS = env.list("ADMINS", subcast=int)
IP = env.str("IP", "localhost")

# Webhook (production uchun)
USE_WEBHOOK     = env.bool("USE_WEBHOOK", False)
WEBHOOK_HOST    = env.str("WEBHOOK_HOST", "https://seb-tech.uz")
WEBHOOK_PATH    = env.str("WEBHOOK_PATH", "/bot/webhook/")
WEBHOOK_URL     = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEBAPP_HOST     = env.str("WEBAPP_HOST", "0.0.0.0")
WEBAPP_PORT     = env.int("WEBAPP_PORT", 3001)

# Django API
API_BASE_URL  = env.str("API_BASE_URL",   "https://sebmarket.uz/api/payments")
DJANGO_BASE_URL = env.str("DJANGO_BASE_URL", "http://127.0.0.1:8000")
BOT_API_PORT    = env.int("BOT_API_PORT",    3002)

# Bepul urinishlar soni (yangi foydalanuvchilarga)
FREE_TRIALS_DEFAULT = 3

# Bot
BOT_USERNAME = "@Sebmarket_bot"

# Boshqa
START_PHOTO_FILE_ID = "AgACAgIAAxkBAAIbHWk4P8fZt-Ir3804yO8XHmusmDw7AAJyEWsbigTBScr0wXcXOjb8AQADAgADeAADNgQ"