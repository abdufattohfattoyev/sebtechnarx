# handlers/users/payment.py - TO'LIQ TUZATILGAN VERSIYA
import asyncio
import logging
from datetime import datetime

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from data.config import ADMINS
from utils.api import api
from keyboards.default.knopkalar import main_menu

# Logger
logger = logging.getLogger(__name__)


# ================ HOLATLAR ================

class PaymentState(StatesGroup):
    waiting_tariff = State()
    waiting_check = State()


# ================ KLAVIATURA FUNKSIYALARI ================

def create_tariff_keyboard(tariffs):
    """API dan olingan tariflar uchun inline klaviatura"""
    markup = InlineKeyboardMarkup(row_width=1)

    for tariff in tariffs:
        price_per_one = tariff['price'] / tariff['count'] if tariff['count'] > 0 else tariff['price']
        button_text = f"💰 {tariff['name']} - {tariff['price']:,.0f} so'm"

        markup.add(
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"tariff_{tariff['id']}"
            )
        )

    markup.add(
        InlineKeyboardButton(
            text="◀️ Orqaga",
            callback_data="back_to_main"
        )
    )

    return markup


def create_payment_keyboard(payment_url):
    """To'lov klaviaturasi"""
    markup = InlineKeyboardMarkup(row_width=1)

    markup.add(
        InlineKeyboardButton(
            text="💳 To'lov qilish (Payme)",
            url=payment_url
        )
    )

    markup.add(
        InlineKeyboardButton(
            text="✅ To'lov qildim - Tekshirish",
            callback_data="check_payment"
        )
    )

    markup.add(
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_payment"
        )
    )

    return markup


# ================ MESSAGE HANDLERS ================

@dp.message_handler(lambda m: m.text == "💰 Hisobni to'ldirish", state='*')
async def show_tariffs(message: types.Message, state: FSMContext):
    """Tariflarni ko'rsatish - INLINE KLAVIATURA"""
    # Avvalgi state ni tozalash
    await state.finish()

    logger.info(f"User {message.from_user.id} started payment process")

    result = await api.get_tariffs()

    if not result or not result.get('success'):
        await message.answer("❌ Tariflar yuklanmadi. Iltimos, keyinroq urinib ko'ring.")
        return

    tariffs = result.get('tariffs', [])

    if not tariffs:
        await message.answer("📋 Hozircha tariflar mavjud emas. Iltimos, keyinroq tekshiring.")
        return

    text = "💰 <b>HISOB TO'LDIRISH</b>\n\n"
    text += "Quyidagi tariflardan birini tanlang:\n\n"

    for tariff in tariffs:
        price_per_one = tariff['price'] / tariff['count'] if tariff['count'] > 0 else tariff['price']
        text += f"<b>{tariff['name']}</b>\n"
        text += f"   • Narxi: {tariff['price']:,.0f} so'm\n"
        text += f"   • Soni: {tariff['count']} ta narxlash\n"
        text += f"   • Bitta: {price_per_one:,.0f} so'm\n\n"

    text += "⬇️ <i>Quyidagi tariflardan birini tanlang:</i>"

    markup = create_tariff_keyboard(tariffs)

    await PaymentState.waiting_tariff.set()
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


# ================ CALLBACK HANDLERS ================

@dp.callback_query_handler(
    lambda c: c.data == "back_to_main",
    state=[PaymentState.waiting_tariff, PaymentState.waiting_check, None]
)
async def back_to_main_callback(callback: types.CallbackQuery, state: FSMContext):
    """Orqaga bosh menyuga"""
    await callback.answer()
    await state.finish()

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete message: {e}")

    await callback.message.answer(
        "🏠 Bosh menyu",
        reply_markup=main_menu(callback.from_user.id in ADMINS)
    )


@dp.callback_query_handler(
    lambda c: c.data and c.data.startswith("tariff_"),
    state=PaymentState.waiting_tariff
)
async def process_tariff_selection(callback: types.CallbackQuery, state: FSMContext):
    """Tarif tanlandi - TO'LOV YARATISH"""
    await callback.answer()

    try:
        tariff_id = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Xato tarif", show_alert=True)
        return

    logger.info(f"User {callback.from_user.id} selected tariff {tariff_id}")

    result = await api.create_payment(
        telegram_id=callback.from_user.id,
        tariff_id=tariff_id
    )

    if not result.get('success'):
        error_msg = result.get('error', 'To\'lov yaratishda xatolik')
        logger.error(f"Payment creation failed for user {callback.from_user.id}: {error_msg}")
        await callback.answer(f"❌ {error_msg}", show_alert=True)
        return

    order_id = result.get('order_id', '')

    if not order_id:
        logger.error(f"Order ID not found in response for user {callback.from_user.id}")
        await callback.answer("❌ Order ID mavjud emas", show_alert=True)
        return

    logger.info(f"Payment created successfully: order_id={order_id}, user={callback.from_user.id}")

    await state.update_data(
        order_id=order_id,
        payment_id=result.get('payment_id'),
        payment_url=result.get('payment_url'),
        amount=result.get('amount'),
        count=result.get('count'),
        tariff_name=result.get('tariff_name'),
        payment_time=datetime.now().isoformat()
    )

    text = f"""💳 <b>TO'LOV MA'LUMOTLARI</b>

🆔 <b>Order ID:</b> <code>{order_id}</code>
🏷️ <b>Tarif:</b> {result.get('tariff_name', '')}
💰 <b>Summa:</b> {result.get('amount', 0):,.0f} so'm
📦 <b>Narxlashlar:</b> {result.get('count', 0)} ta

<b>To'lov qilish uchun:</b>
1️⃣ Quyidagi tugma orqali Payme ga o'ting
2️⃣ To'lovni amalga oshiring
3️⃣ To'lov avtomatik tekshiriladi (15 soniya)

⏳ To'lov 30 daqiqa ichida amalga oshirilishi kerak!
"""

    markup = create_payment_keyboard(result.get('payment_url', ''))

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete message: {e}")

    await PaymentState.waiting_check.set()
    await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")

    # Avtomatik tekshirishni ishga tushirish
    asyncio.create_task(auto_check_payment(order_id, callback.from_user.id, state))


async def auto_check_payment(order_id: str, user_id: int, state: FSMContext):
    """
    Avtomatik to'lov tekshirish - ORDER_ID orqali
    Har 15 soniyada 10 marta tekshiradi (2.5 daqiqa)
    """
    try:
        logger.info(f"🔄 Auto check started: order_id={order_id}, user={user_id}")

        for attempt in range(10):  # 10 marta tekshirish
            await asyncio.sleep(15)  # Har 15 soniyada

            # State hali active ekanligini tekshirish
            try:
                current_state = await state.get_state()
                if current_state != PaymentState.waiting_check.state:
                    logger.info(f"❌ State changed, stopping auto check: order_id={order_id}")
                    return
            except Exception as e:
                logger.error(f"State check error: {e}")
                return

            logger.info(f"🔍 Checking payment: order_id={order_id}, attempt={attempt + 1}/10")

            result = await api.check_payment_status(order_id)

            if result.get('success') and result.get('has_payment'):
                payment_state = result.get('state')

                if payment_state == 2:  # To'landi
                    logger.info(f"✅ Payment completed automatically: order_id={order_id}, user={user_id}")

                    text = f"""✅ <b>TO'LOV MUVAFFAQIYATLI!</b>

💰 <b>Balans:</b> {result.get('balance', 0)} ta narxlash
📦 <b>Qo'shildi:</b> {result.get('count', 0)} ta
💵 <b>Summa:</b> {result.get('amount', 0):,.0f} so'm

🎉 Endi siz telefonlarni narxlashingiz mumkin!
"""
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            reply_markup=main_menu(user_id in ADMINS),
                            parse_mode="HTML"
                        )
                        logger.info(f"✅ Success message sent to user {user_id}")
                    except Exception as e:
                        logger.error(f"Failed to send success message: {e}")

                    await state.finish()
                    return

                elif payment_state == 1:  # Kutilmoqda
                    logger.info(f"⏳ Payment pending: order_id={order_id}, attempt={attempt + 1}")

                elif payment_state == -1:  # Bekor qilindi
                    logger.warning(f"❌ Payment cancelled: order_id={order_id}")

                    text = "❌ <b>TO'LOV BEKOR QILINDI</b>\n\nIltimos, qaytadan urinib ko'ring."
                    try:
                        await bot.send_message(
                            chat_id=user_id,
                            text=text,
                            reply_markup=main_menu(user_id in ADMINS),
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Failed to send cancellation message: {e}")

                    await state.finish()
                    return
            else:
                logger.info(f"⏳ Payment not found yet: order_id={order_id}, attempt={attempt + 1}")

        logger.info(f"⏱️ Auto check finished without success: order_id={order_id}")

        # 10 marta tekshirishdan keyin xabar yuborish
        text = """⏱️ <b>TO'LOV TEKSHIRUVI TUGADI</b>

To'lov hali tasdiqlanmadi. 

Agar to'lovni amalga oshirgan bo'lsangiz:
• "✅ To'lov qildim" tugmasini bosing
• Yoki biroz kutib qayta tekshiring

Agar to'lov amalga oshmagan bo'lsa:
• Qaytadan urinib ko'ring
"""
        try:
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Failed to send timeout message: {e}")

    except Exception as e:
        logger.error(f"❌ Auto check payment error: order_id={order_id}, error={e}", exc_info=True)


@dp.callback_query_handler(
    lambda c: c.data == "check_payment",
    state=PaymentState.waiting_check
)
async def check_payment_callback(callback: types.CallbackQuery, state: FSMContext):
    """To'lovni tekshirish - ORDER_ID orqali"""
    await callback.answer("🔄 Tekshirilmoqda...")

    data = await state.get_data()
    order_id = data.get('order_id')

    if not order_id:
        logger.error(f"Order ID not found in state for user {callback.from_user.id}")
        await callback.answer(
            "❌ Order ID topilmadi. Iltimos, qaytadan urinib ko'ring.",
            show_alert=True
        )
        return

    logger.info(f"Manual check payment: order_id={order_id}, user={callback.from_user.id}")

    result = await api.check_payment_status(order_id)

    if not result.get('success'):
        logger.warning(f"Payment check failed: order_id={order_id}")
        await callback.answer(
            "❌ To'lov topilmadi. Iltimos, to'lovni amalga oshiring va keyin tekshiring.",
            show_alert=True
        )
        return

    if result.get('has_payment'):
        payment_state = result.get('state')

        if payment_state == 2:  # To'landi
            logger.info(f"✅ Payment completed: order_id={order_id}, user={callback.from_user.id}")

            text = f"""✅ <b>TO'LOV MUVAFFAQIYATLI!</b>

💰 <b>Balans:</b> {result.get('balance', 0)} ta narxlash
📦 <b>Qo'shildi:</b> {result.get('count', 0)} ta
💵 <b>Summa:</b> {result.get('amount', 0):,.0f} so'm

🎉 Endi siz telefonlarni narxlashingiz mumkin!
"""
            try:
                await callback.message.edit_text(text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Could not edit message: {e}")
                await callback.message.answer(
                    text,
                    reply_markup=main_menu(callback.from_user.id in ADMINS),
                    parse_mode="HTML"
                )

            await state.finish()
            await callback.answer("✅ To'lov muvaffaqiyatli!")

        elif payment_state == 1:  # Kutilmoqda
            logger.info(f"Payment pending: order_id={order_id}")
            await callback.answer(
                "⏳ To'lov hali amalga oshirilmadi.\n"
                "Iltimos, to'lovni amalga oshiring va keyin qayta tekshiring.",
                show_alert=True
            )

        else:  # Bekor qilindi yoki boshqa holat
            logger.warning(f"Payment cancelled or invalid state: order_id={order_id}, state={payment_state}")
            await callback.answer(
                "❌ To'lov bekor qilindi yoki vaqti tugadi.\n"
                "Iltimos, qaytadan urinib ko'ring.",
                show_alert=True
            )
            await state.finish()
    else:
        logger.warning(f"Payment not found: order_id={order_id}")
        await callback.answer(
            "❌ To'lov topilmadi. Iltimos, to'lovni amalga oshiring.",
            show_alert=True
        )


@dp.callback_query_handler(
    lambda c: c.data == "cancel_payment",
    state=PaymentState.waiting_check
)
async def cancel_payment_callback(callback: types.CallbackQuery, state: FSMContext):
    """To'lovni bekor qilish"""
    data = await state.get_data()
    order_id = data.get('order_id', 'unknown')

    logger.info(f"User cancelled payment: order_id={order_id}, user={callback.from_user.id}")

    await callback.answer("❌ To'lov bekor qilindi")

    try:
        await callback.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete message: {e}")

    await state.finish()

    await callback.message.answer(
        "🏠 Bosh menyu",
        reply_markup=main_menu(callback.from_user.id in ADMINS)
    )


# ================ BALANS KO'RISH ================

@dp.message_handler(lambda m: m.text == "💤 Mening hisobim", state='*')
async def show_my_account(message: types.Message, state: FSMContext):
    """Balansni ko'rsatish"""
    # State ni tozalash
    await state.finish()

    logger.info(f"User {message.from_user.id} checking account")

    result = await api.get_balance(message.from_user.id)

    if not result.get('success'):
        logger.error(f"Failed to get balance for user {message.from_user.id}")
        await message.answer("❌ Ma'lumotlar yuklanmadi. Iltimos, keyinroq urinib ko'ring.")
        return

    balance = result.get('balance', 0)
    full_name = result.get('full_name', message.from_user.full_name)

    text = f"""💤 <b>SHAXSIY KABINET</b>

💤 <b>Ism:</b> {full_name}
🆔 <b>ID:</b> <code>{message.from_user.id}</code>
💰 <b>Balans:</b> {balance} ta narxlash
"""

    if balance <= 0:
        text += "\n⚠️ <b>Balans yetarli emas!</b>\n"
        text += "Balansni to'ldirish uchun <b>'💰 Hisobni to'ldirish'</b> tugmasini bosing."

    await message.answer(text, parse_mode="HTML")