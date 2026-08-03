# handlers/users/payment.py — TO'LOV HOLATLARI
#
# DIQQAT: to'lovning O'ZI shu faylda emas, `handlers/users/start.py` da.
#
# Ilgari bu yerda butun to'lov oqimi takrorlangan edi: "💰 Hisobni
# to'ldirish", tarif tanlash, to'lovni tekshirish, bekor qilish, "👤 Mening
# hisobim". Ularning HECH BIRI ishlamasdi: `handlers/users/__init__.py` da
# `start` `payment` dan oldin import qilinadi, aiogram esa bir xil shartga
# mos birinchi handlerni oladi — ya'ni har doim `start.py` niki yutardi.
#
# Bu shunchaki ortiqcha kod emas, tuzoq edi: bu yerdagi narx yoki matnni
# tuzatgan odam bot xuddi shu eskisicha ishlayverganini ko'rardi va sababini
# tushunmasdi. Shuning uchun takrorlar olib tashlandi va faqat ROSTDAN ham
# ishlaydigani qoldirildi.

import logging

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from loader import dp
from data.config import ADMINS
from keyboards.default.knopkalar import main_menu

logger = logging.getLogger(__name__)


# ================ HOLATLAR ================

class PaymentState(StatesGroup):
    """To'lov holatlari. `start.py` shu holatlar bilan ishlaydi."""
    waiting_tariff = State()
    waiting_check = State()


# ================ CALLBACK HANDLERS ================

@dp.callback_query_handler(
    lambda c: c.data == "back_to_main",
    state=[PaymentState.waiting_tariff, PaymentState.waiting_check, None]
)
async def back_to_main_callback(callback: types.CallbackQuery, state: FSMContext):
    """
    Tariflar ro'yxatidagi "◀️ Orqaga" — bosh menyuga qaytaradi.

    `start.py` da bu callback uchun handler yo'q, shuning uchun u shu yerda
    qoladi: `create_tariffs_inline_keyboard()` aynan shu `back_to_main` ni
    yuboradi va usiz tugma jim qolardi.
    """
    await callback.answer()
    await state.finish()

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Xabarni o'chirib bo'lmadi: {e}")

    await callback.message.answer(
        "🏠 Bosh menyu",
        reply_markup=main_menu(callback.from_user.id in ADMINS)
    )
