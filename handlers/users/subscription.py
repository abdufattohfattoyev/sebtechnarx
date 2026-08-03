# utils/misc/subscription.py - MAJBURIY OBUNA TIZIMI (TO'LIQ TUZATILGAN)
import logging

from aiogram import types
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.exceptions import (
    BadRequest,
    ChatNotFound,
    Unauthorized,
)
from keyboards.uslub import ibtn, YASHIL, KOK
from loader import bot

logger = logging.getLogger(__name__)

# ============= KANAL SOZLAMALARI =============
CHANNEL_USERNAME = "@sebtech1"  # @ belgisi bilan
CHANNEL_URL = "https://t.me/sebtech1"
CHANNEL_ID = -1001913215598

# Bot kanalda admin emasligi haqidagi ogohlantirish faqat bir marta yozilsin
_admin_warning_shown = False


# ============= OBUNA TEKSHIRISH =============
async def check_subscription(user_id: int) -> bool:
    """
    Foydalanuvchi kanalga obuna bo'lganini tekshirish

    Returns:
        True - obuna bo'lgan
        False - obuna emas

    Eslatma: tekshirishning o'zi imkonsiz bo'lsa (bot kanalda admin emas,
    kanal topilmadi, Telegram xatosi) - foydalanuvchini to'smaymiz, True.
    """
    global _admin_warning_shown

    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
        # Status: creator, administrator, member - obuna
        # Status: left, kicked - obuna emas
        return member.status in ['creator', 'administrator', 'member']

    except (ChatNotFound, Unauthorized, BadRequest) as e:
        # Eng ko'p uchraydigani: "member list is inaccessible" -
        # ya'ni bot {CHANNEL_USERNAME} kanalida admin emas.
        if not _admin_warning_shown:
            _admin_warning_shown = True
            logger.warning(
                f"⚠️ Obunani tekshirib bo'lmadi ({e}). "
                f"Botni {CHANNEL_USERNAME} kanaliga ADMIN qilib qo'ying, "
                f"aks holda majburiy obuna ishlamaydi (hamma o'tkaziladi)."
            )
        return True

    except Exception as e:
        logger.error(f"❌ Obuna tekshirishda kutilmagan xato: {e}")
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