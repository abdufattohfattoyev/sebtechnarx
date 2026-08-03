from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage

import data.config as config  # ✅ aniq import (kolliziya bo'lmaydi)

from utils.emoji import botga_ulash

bot = Bot(token=config.BOT_TOKEN, parse_mode=types.ParseMode.HTML)

# Xabarlardagi tanish emojilar animatsion (custom) emojiga aylantiriladi.
# Bir joyda ulanadi — `utils/emoji.py` dagi izohga qarang.
botga_ulash(bot)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
