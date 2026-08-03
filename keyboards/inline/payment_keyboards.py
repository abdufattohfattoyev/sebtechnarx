# keyboards/inline/payment_keyboards.py
#
# Ranglar `keyboards/uslub.py` da: YASHIL — asosiy harakat, KO'K — yordamchi
# yo'l, QIZIL — bekor qilish.

from aiogram.types import InlineKeyboardMarkup

from keyboards.uslub import ibtn, YASHIL, KOK, QIZIL, NAV


def tarif_satri(tariff) -> str:
    """
    Tarifning YAGONA yozilishi — xabar matnida ham, tugmada ham shu.

    Ilgari ikkalasi alohida yozilardi: matnda "2️⃣ 2 ta narxlash / 10,000
    so'm", tugmada esa "💰 2 ta narxlash - 10,000 so'm". Odam ro'yxatni
    o'qib, pastdan tugumani izlaganda ikkisini solishtirishga majbur
    bo'lardi. Endi bitta funksiya — farq qilishining iloji yo'q.

    Raqamli emoji (2️⃣) ataylab ishlatilmadi: sakkiz to'plamning
    birortasida ham uning animatsion varianti yo'q, tarif nomi esa
    sonni allaqachon aytib turibdi ("2 ta narxlash").
    """
    return f"💰 {tariff['name']} — {tariff['price']:,.0f} so'm"


def create_tariffs_inline_keyboard(tariffs):
    """Tariflar uchun inline klaviatura yaratish"""
    markup = InlineKeyboardMarkup(row_width=1)

    # Tariflar teng variantlar: bittasini yashil qilish "to'g'risi shu"
    # degan taassurot beradi, holbuki tanlov odamning o'zida.
    for tariff in tariffs:
        markup.add(ibtn(tarif_satri(tariff), KOK,
                        callback_data=f"tariff_{tariff['id']}"))

    markup.add(ibtn("◀️ Orqaga", NAV, callback_data="back_to_main"))

    return markup


def create_payment_inline_keyboard(payment_url):
    """To'lov uchun inline klaviatura yaratish"""
    markup = InlineKeyboardMarkup(row_width=1)

    # To'lov havolasi — odam shu ekranga aynan shuning uchun kelgan.
    markup.add(ibtn("💳 To'lov qilish", YASHIL, url=payment_url))
    markup.add(ibtn("✅ To'lov qildim", KOK, callback_data="check_payment"))
    markup.add(ibtn("❌ Bekor qilish", QIZIL, callback_data="cancel_payment"))

    return markup
