# keyboards/inline/payment_keyboards.py
#
# Ranglar `keyboards/uslub.py` da: YASHIL — asosiy harakat, KO'K — yordamchi
# yo'l, QIZIL — bekor qilish.

from aiogram.types import InlineKeyboardMarkup

from keyboards.uslub import ibtn, YASHIL, KOK, QIZIL


def create_tariffs_inline_keyboard(tariffs):
    """Tariflar uchun inline klaviatura yaratish"""
    markup = InlineKeyboardMarkup(row_width=1)

    # Tariflar teng variantlar: bittasini yashil qilish "to'g'risi shu"
    # degan taassurot beradi, holbuki tanlov odamning o'zida.
    for tariff in tariffs:
        button_text = f"💰 {tariff['name']} - {tariff['price']:,.0f} so'm"
        markup.add(ibtn(button_text, KOK, callback_data=f"tariff_{tariff['id']}"))

    markup.add(ibtn("◀️ Orqaga", KOK, callback_data="back_to_main"))

    return markup


def create_payment_inline_keyboard(payment_url):
    """To'lov uchun inline klaviatura yaratish"""
    markup = InlineKeyboardMarkup(row_width=1)

    # To'lov havolasi — odam shu ekranga aynan shuning uchun kelgan.
    markup.add(ibtn("💳 To'lov qilish", YASHIL, url=payment_url))
    markup.add(ibtn("✅ To'lov qildim", KOK, callback_data="check_payment"))
    markup.add(ibtn("❌ Bekor qilish", QIZIL, callback_data="cancel_payment"))

    return markup
