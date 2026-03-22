from aiogram import types
from aiogram.dispatcher import FSMContext

from loader import dp
from keyboards.default.knopkalar import main_menu
from data.config import ADMINS


@dp.message_handler(state=None)
async def bot_echo(message: types.Message):
    await message.answer(
        "🏠 Bosh menyuga qaytish uchun /start bosing.",
        reply_markup=main_menu(message.from_user.id in ADMINS)
    )
