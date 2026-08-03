# utils/misc/subscription.py - MAJBURIY OBUNA TIZIMI (TO'LIQ TUZATILGAN)
from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from keyboards.uslub import ibtn, YASHIL, KOK
from loader import bot

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
    """Obuna bo'lish tugmasi"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    # Birinchi qadam YASHIL: obuna bo'lmaguncha bot ochilmaydi.
    keyboard.add(ibtn("📢 Kanalga obuna bo'lish", YASHIL, url=CHANNEL_URL))
    # Ikkinchisi ko'k: u obunadan KEYIN bosiladi, avval emas.
    keyboard.add(ibtn("✅ Obuna bo'ldim, tekshiring", KOK,
                      callback_data="check_subscription"))
    return keyboard


# ============= OBUNA XABARI =============
SUBSCRIPTION_TEXT = """🔐 <b>Botdan foydalanish uchun kanalimizga obuna bo'ling!</b>

📢 <b>Kanal:</b> {channel}

<b>Obunadan so'ng "✅ Obuna bo'ldim" tugmasini bosing!</b>
"""