# utils/misc/subscription.py - MAJBURIY OBUNA TIZIMI (FIXED)

from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import bot, dp

# ============= KANAL SOZLAMALARI =============
CHANNEL_USERNAME = "@sebtech1"  # @ belgisi bilan
CHANNEL_URL = "https://t.me/sebtech1"
CHANNEL_ID = -1001913215598


# ============= OBUNA TEKSHIRISH =============
async def check_subscription(user_id: int) -> bool:
    """
    Foydalanuvchi kanalga obuna bo'lganini tekshirish

    Returns:
        True - obuna bo'lgan
        False - obuna emas
    """
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)

        # Status: creator, administrator, member - obuna
        # Status: left, kicked - obuna emas
        if member.status in ['creator', 'administrator', 'member']:
            return True
        else:
            return False

    except Exception as e:
        print(f"❌ Obuna tekshirishda xato: {e}")
        # Xato bo'lsa, davom ettirish uchun True qaytarish
        return True


# ============= OBUNA TUGMASI =============
def subscription_keyboard() -> InlineKeyboardMarkup:
    """
    Obuna bo'lish tugmasi
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(
            text="📢 Kanalga obuna bo'lish",
            url=CHANNEL_URL
        )
    )
    keyboard.add(
        InlineKeyboardButton(
            text="✅ Obuna bo'ldim, tekshiring",
            callback_data="check_subscription"
        )
    )
    return keyboard


# ============= OBUNA XABARI =============
SUBSCRIPTION_TEXT = """🔐 <b>Botdan foydalanish uchun kanalimizga obuna bo'ling!</b>

<b>Obunadan so'ng "✅ Obuna bo'ldim" tugmasini bosing!</b>
"""


# ============= OBUNA CALLBACK HANDLER =============
@dp.callback_query_handler(lambda c: c.data == "check_subscription", state="*")
async def check_subscription_callback(call: types.CallbackQuery):
    """
    "✅ Obuna bo'ldim" tugmasi bosilganda
    """
    await call.answer("🔄 Tekshirilmoqda...")

    is_subscribed = await check_subscription(call.from_user.id)

    if is_subscribed:
        try:
            await call.message.delete()
        except:
            pass

        await call.message.answer(
            "✅ <b>Obuna tasdiqlandi!</b>\n\n"
            "🎉 Endi botdan to'liq foydalanishingiz mumkin!\n\n"
            "Iltimos, /start buyrug'ini bosing!",
            parse_mode="HTML"
        )
    else:
        await call.answer(
            "❌ Siz hali obuna bo'lmagansiz!\n\n"
            "📢 Kanalga obuna bo'lib, qaytadan tugmani bosing.",
            show_alert=True
        )


# ============= OBUNA DECORATOR =============
def subscription_required(handler):
    """
    Decorator - obuna majburiy qilish uchun

    Foydalanish:
    @subscription_required
    async def my_handler(message: types.Message):
        ...
    """

    async def wrapper(event, *args, **kwargs):
        # Message yoki CallbackQuery
        if isinstance(event, types.Message):
            user_id = event.from_user.id
            chat = event
        elif isinstance(event, types.CallbackQuery):
            user_id = event.from_user.id
            chat = event.message
        else:
            return await handler(event, *args, **kwargs)

        # Obuna tekshirish
        is_subscribed = await check_subscription(user_id)

        if not is_subscribed:
            await chat.answer(
                SUBSCRIPTION_TEXT,
                reply_markup=subscription_keyboard(),
                parse_mode="HTML"
            )
            return

        # Obuna bo'lsa - handler ishlatish
        return await handler(event, *args, **kwargs)

    return wrapper