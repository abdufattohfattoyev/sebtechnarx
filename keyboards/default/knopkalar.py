# keyboards/default/knopkalar.py - AIOGRAM 2.25.2
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

MINIAPP_URL = "https://seb-tech.uz/miniapp/"


# ================ ASOSIY KLAVIATURALAR ================

def phone_request_kb():
    """Telefon raqam so'rash"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    return kb


def main_menu(is_admin=False):
    """Asosiy menyu - ODDIY FOYDALANUVCHI"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # Mini App tugmasi — eng yuqorida
    # kb.row(KeyboardButton("🌐 Mini App", web_app=WebAppInfo(url=MINIAPP_URL)))

    # Birinchi qator - Asosiy funksiyalar
    kb.row(KeyboardButton("📱 Telefon narxlash"))

    # Ikkinchi qator - To'lov va Hisob
    kb.row(
        KeyboardButton("💰 Hisobni to'ldirish"),
        KeyboardButton("👤 Mening hisobim")
    )

    # Uchinchi qator - Xaridlar va kafolat
    # kb.row(
    #     KeyboardButton("🛍 Mening xaridlarim"),
    #     KeyboardButton("🛡 Kafolat"),
    # )

    # To'rtinchi qator - Qo'shimcha
    kb.row(KeyboardButton("ℹ️ Biz haqimizda"))

    # Admin uchun alohida panel
    if is_admin:
        kb.row(KeyboardButton("🔧 Admin panel"))

    return kb


def back_kb():
    """Orqaga va Bosh menyu"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
    return kb


def cancel_kb():
    """Bekor qilish"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("❌ Bekor qilish"))
    return kb


# ================ TO'LOV KLAVIATURALARI ================

def balance_menu_kb():
    """Balans menu"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("💰 Hisobni to'ldirish"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb


def payment_menu_kb():
    """To'lov tariflari"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        KeyboardButton("1️⃣ 1 marta - 5,000 so'm"),
        KeyboardButton("5️⃣ 5 marta - 20,000 so'm")
    )
    kb.add(KeyboardButton("🔟 10 marta - 35,000 so'm"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb


def payment_check_inline_kb(payment_url):
    """
    Inline klaviatura - To'lovni tekshirish (AIOGRAM 2.25.2)

    Args:
        payment_url (str): Payme to'lov havolasi
    """
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("💳 To'lov qilish", url=payment_url)
    )
    markup.add(
        InlineKeyboardButton("🔄 To'lovni tekshirish", callback_data="check_payment")
    )
    markup.add(
        InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_payment")
    )
    return markup


# ================ NARXLASH KLAVIATURALARI ================

def create_keyboard(items, row_width=2, back=True, main_menu=True):
    """
    Dinamik klaviatura yaratish

    Args:
        items: tugmalar ro'yxati
        row_width: har bir qatordagi tugmalar soni
        back: "Orqaga" tugmasini qo'shish
        main_menu: "Bosh menyu" tugmasini qo'shish
    """
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # Asosiy tugmalar
    for i in range(0, len(items), row_width):
        row_items = items[i:i + row_width]
        kb.row(*[KeyboardButton(item) for item in row_items])

    # Qo'shimcha tugmalar
    extra_buttons = []
    if back:
        extra_buttons.append(KeyboardButton("◀️ Orqaga"))
    if main_menu:
        extra_buttons.append(KeyboardButton("🏠 Bosh menyu"))

    if extra_buttons:
        kb.row(*extra_buttons)

    return kb


def parts_choice_kb():
    """Almashgan qism bormi/yo'q"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Ha"), KeyboardButton("❌ Yo'q"))
    kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
    return kb


def create_parts_inline_kb(selected_parts, parts_dict):
    """Inline klaviatura - Qismlarni tanlash (AIOGRAM 2.25.2)"""
    markup = InlineKeyboardMarkup(row_width=2)

    for key, name in parts_dict.items():
        text = f"{'✅' if key in selected_parts else '☐'} {name}"
        markup.insert(InlineKeyboardButton(text, callback_data=f"part_{key}"))

    markup.row(
        InlineKeyboardButton(
            f"✅ Davom etish ({len(selected_parts)}/3)",
            callback_data="part_done"
        )
    )

    return markup


# ================ MANBA KLAVIATURASI ================

# def source_inline_kb():
#     """Qayerdan keldi — inline"""
#     kb = InlineKeyboardMarkup(row_width=2)
#     kb.add(
#         InlineKeyboardButton("📱 Telegram",          callback_data="src_telegram"),
#         InlineKeyboardButton("📸 Instagram",         callback_data="src_instagram"),
#         InlineKeyboardButton("🤝 Do'st taklifi",     callback_data="src_referral"),
#         InlineKeyboardButton("🚶 O'zi keldi",        callback_data="src_walkin"),
#         InlineKeyboardButton("🔄 Avval ham kelgan",  callback_data="src_repeat"),
#         InlineKeyboardButton("🔹 Boshqa",            callback_data="src_other"),
#     )
#     return kb


# ================ BAHOLASH KLAVIATURASI ================

# def rating_inline_kb(sale_id: int):
#     """Sotuvchini baholash — 5 yulduz inline"""
#     kb = InlineKeyboardMarkup(row_width=5)
#     stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
#     kb.row(*[
#         InlineKeyboardButton(stars[i], callback_data=f"rate_{i+1}_{sale_id}")
#         for i in range(5)
#     ])
#     kb.row(InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data=f"rate_skip_{sale_id}"))
#     return kb


# def rating_comment_skip_kb(sale_id: int):
#     """Izoh yoki o'tkazib yuborish"""
#     kb = InlineKeyboardMarkup()
#     kb.add(InlineKeyboardButton("⏭ Izoхsiz yuborish", callback_data=f"rate_nocomment_{sale_id}"))
#     return kb


# ================ BAHOLASH KLAVIATURALARI ================

# def rating_inline_kb(sale_id: int):
#     """Sotuvchini baholash — 1 dan 5 gacha raqamlar"""
#     kb = InlineKeyboardMarkup(row_width=5)
#     kb.row(
#         InlineKeyboardButton("1", callback_data=f"rate_1_{sale_id}"),
#         InlineKeyboardButton("2", callback_data=f"rate_2_{sale_id}"),
#         InlineKeyboardButton("3", callback_data=f"rate_3_{sale_id}"),
#         InlineKeyboardButton("4", callback_data=f"rate_4_{sale_id}"),
#         InlineKeyboardButton("5", callback_data=f"rate_5_{sale_id}"),
#     )
#     kb.row(InlineKeyboardButton("⏭ O'tkazib yuborish", callback_data=f"rate_skip_{sale_id}"))
#     return kb


# RATING_REASONS = {
#     'svc':    "😤 Xizmat yomon edi",
#     'price':  "💰 Narx qimmat edi",
#     'wait':   "⏰ Kutish uzoq bo'ldi",
#     'cond':   "📦 Telefon holati mos kelmadi",
#     'manner': "🤝 Sotuvchi muomalasi yoqmadi",
#     'info':   "📋 Telefon haqida kam tushuntirdi",
#     'other':  "📝 Boshqa sabab",
# }


# def rating_reason_kb(sale_id: int, rating: int):
#     """1-4 baho uchun sabab tanlash"""
#     kb = InlineKeyboardMarkup(row_width=2)
#     for key, label in RATING_REASONS.items():
#         kb.insert(InlineKeyboardButton(label, callback_data=f"rsn_{key}_{sale_id}_{rating}"))
#     return kb


# ================ ADMIN KLAVIATURALARI ================

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # Birinchi qator - Statistika va Ma'lumotlar
    kb.row(
        KeyboardButton("📊 Statistika"),
        KeyboardButton("💳 Tariflar")
    )

    # Ikkinchi qator - Import va Export
    kb.row(
        KeyboardButton("📥 Narxlarni import qilish"),
        KeyboardButton("📢 Reklama")
    )

    # Uchinchi qator - Foydalanuvchi boshqaruvi
    kb.row(
        KeyboardButton("👤 Foydalanuvchi"),
        KeyboardButton("🛍 Mijoz xaridlari")
    )

    # To'rtinchi qator - Qo'shimcha funksiyalar
    kb.row(
        KeyboardButton("📱 Namuna"),
        KeyboardButton("🗑 Narxlarni tozalash")
    )

    # Beshinchi qator - Rejimlar
    kb.row(
        KeyboardButton("🔧 Tamirlash rejimi"),
        KeyboardButton("🆓 Bepul/Pullik rejim")
    )

    # Oltinchi qator - Orqaga
    kb.row(KeyboardButton("🏠 Bosh menyu"))

    return kb


def maintenance_kb():
    """Tamirlash rejimi menu"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # Birinchi qator - Asosiy boshqaruv
    kb.row(KeyboardButton("🔴 Barchasini yopish"))
    kb.row(KeyboardButton("🟢 Barchasini ochish"))

    # Ikkinchi qator - Bo'limlar
    kb.row(
        KeyboardButton("📱 Narxlash"),
        KeyboardButton("💰 To'lov")
    )
    kb.row(
        KeyboardButton("👤 Hisob"),
        KeyboardButton("📊 Holat")
    )

    # Uchinchi qator - Orqaga
    kb.row(KeyboardButton("◀️ Orqaga"))

    return kb


def cleanup_confirm_kb():
    """Bazani tozalash tasdiqlash"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("✅ Ha, tozalash"),
        KeyboardButton("❌ Yo'q, bekor qilish")
    )
    kb.row(KeyboardButton("🏠 Bosh menyu"))
    return kb
