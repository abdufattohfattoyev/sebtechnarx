# data/config.py
from environs import Env

env = Env()
env.read_env()

BOT_TOKEN = env.str("BOT_TOKEN")
# ADMINS ni list sifatida olish — bu juda muhim!
ADMINS = env.list("ADMINS", subcast=int)  # vergul bilan ajratilgan raqamlarni list qiladi
IP = env.str("IP", "localhost")
START_PHOTO_FILE_ID = "AgACAgIAAxkBAAIbHWk4P8fZt-Ir3804yO8XHmusmDw7AAJyEWsbigTBScr0wXcXOjb8AQADAgADeAADNgQ"