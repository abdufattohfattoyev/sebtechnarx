# keyboards/inline/payment_keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def create_tariffs_inline_keyboard(tariffs):
    """Tariflar uchun inline klaviatura yaratish"""
    markup = InlineKeyboardMarkup(row_width=1)

    for tariff in tariffs:
        price_per_one = tariff['price'] / tariff['count']
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


def create_payment_inline_keyboard(payment_url):
    """To'lov uchun inline klaviatura yaratish"""
    markup = InlineKeyboardMarkup(row_width=1)

    markup.add(
        InlineKeyboardButton(
            text="💳 To'lov qilish",
            url=payment_url
        )
    )

    markup.add(
        InlineKeyboardButton(
            text="✅ To'lov qildim",
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