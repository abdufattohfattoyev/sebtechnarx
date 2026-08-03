# keyboards/default/knopkalar.py - AIOGRAM 2.25.2
#
# Tugmalar RANGLI: `keyboards/uslub.py` dagi `btn` / `ibtn` har bir tugmaga
# `style` maydonini qo'shadi. Rang qoidasi bitta joyda turadi:
#
#   YASHIL — ekrandagi asosiy harakat (odam shu tugma uchun kelgan)
#   KO'K   — yordamchi yo'l, navigatsiya, ro'yxat
#   QIZIL  — bekor qilish, o'chirish, ortga qaytarib bo'lmaydigan tanlov
#
# Rang faqat ko'zni yo'naltiradi: eski Telegram mijozlarida tugma kulrang
# chiqadi va matnning o'zi hamon hamma narsani aytib turishi kerak.

from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, WebAppInfo

from keyboards.uslub import btn, ibtn, YASHIL, KOK, QIZIL, NAV

MINIAPP_URL = "https://seb-tech.uz/miniapp/"


# ================ ASOSIY KLAVIATURALAR ================

def phone_request_kb():
    """Telefon raqam so'rash"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    # YASHIL — bu ekrandagi YAGONA harakat, boshqa yo'l yo'q.
    kb.add(btn("📱 Telefon raqamni yuborish", YASHIL, request_contact=True))
    return kb


def main_menu(is_admin=False):
    """Asosiy menyu - ODDIY FOYDALANUVCHI"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)

    # Mini App tugmasi — eng yuqorida
    # kb.row(btn("🌐 Mini App", YASHIL, web_app=WebAppInfo(url=MINIAPP_URL)))

    # Birinchi qator - botning asosiy ishi. Butun kenglikda va YASHIL:
    # foydalanuvchilarning aksariyati aynan shu tugma uchun keladi va uni
    # menyudagi qolgan hamma narsadan oldin ko'rishi kerak.
    kb.row(btn("📱 Telefon narxlash", YASHIL))

    # Ikkinchi qator - To'lov va Hisob (yordamchi yo'llar)
    kb.row(
        btn("💰 Hisobni to'ldirish", KOK),
        btn("👤 Mening hisobim", KOK),
    )

    # Uchinchi qator - Xaridlar va kafolat
    # kb.row(
    #     btn("🛍 Mening xaridlarim", KOK),
    #     btn("🛡 Kafolat", KOK),
    # )

    # To'rtinchi qator - Qo'shimcha
    kb.row(btn("ℹ️ Biz haqimizda", KOK))

    # Admin uchun alohida panel
    if is_admin:
        kb.row(btn("🔧 Admin panel", KOK))

    return kb


def back_kb():
    """Orqaga va Bosh menyu"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(btn("◀️ Orqaga", NAV), btn("🏠 Bosh menyu", NAV))
    return kb


def cancel_kb():
    """Bekor qilish"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(btn("❌ Bekor qilish", QIZIL))
    return kb


# ================ TO'LOV KLAVIATURALARI ================

def balance_menu_kb():
    """Balans menu"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(btn("💰 Hisobni to'ldirish", YASHIL))
    kb.add(btn("◀️ Orqaga", NAV))
    return kb


# `payment_menu_kb()` OLIB TASHLANDI.
#
# U tariflarni QO'LDA yozib qo'yardi ("1 marta - 5,000 so'm") va hech qayerdan
# chaqirilmasdi — ya'ni bazadagi haqiqiy narxlar o'zgarganda ham eski narxni
# ko'rsatib turaverardi. Tariflar endi FAQAT bitta manbadan keladi:
# Django `/api/payments/tariffs/` → `create_tariffs_inline_keyboard()`.
# Narxni o'zgartirish uchun `payments/tariflar.py` tahrirlanadi.


def payment_check_inline_kb(payment_url):
    """
    Inline klaviatura - To'lovni tekshirish (AIOGRAM 2.25.2)

    Args:
        payment_url (str): Payme to'lov havolasi
    """
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(ibtn("💳 To'lov qilish", YASHIL, url=payment_url))
    markup.add(ibtn("🔄 To'lovni tekshirish", KOK, callback_data="check_payment"))
    markup.add(ibtn("❌ Bekor qilish", QIZIL, callback_data="cancel_payment"))
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

    # Asosiy tugmalar — model, xotira, holat kabi TANLOVLAR. Hammasi KO'K:
    # ular teng variantlar, orasidan bittasini rang bilan ajratib bo'lmaydi.
    for i in range(0, len(items), row_width):
        row_items = items[i:i + row_width]
        kb.row(*[btn(str(item), KOK) for item in row_items])

    # Qo'shimcha tugmalar
    extra_buttons = []
    if back:
        extra_buttons.append(btn("◀️ Orqaga", NAV))
    if main_menu:
        extra_buttons.append(btn("🏠 Bosh menyu", NAV))

    if extra_buttons:
        kb.row(*extra_buttons)

    return kb


def parts_choice_kb():
    """Almashgan qism bormi/yo'q"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(btn("✅ Ha", YASHIL), btn("❌ Yo'q", QIZIL))
    kb.row(btn("◀️ Orqaga", NAV), btn("🏠 Bosh menyu", NAV))
    return kb


def create_parts_inline_kb(selected_parts, parts_dict):
    """Inline klaviatura - Qismlarni tanlash (AIOGRAM 2.25.2)"""
    markup = InlineKeyboardMarkup(row_width=2)

    for key, name in parts_dict.items():
        tanlangan = key in selected_parts
        text = f"{'✅' if tanlangan else '☐'} {name}"
        # Tanlangan qism YASHIL — belgidan tashqari rang ham ko'rsatib
        # tursa, ro'yxatdan ko'z bilan o'tish osonlashadi.
        markup.insert(ibtn(text, YASHIL if tanlangan else KOK,
                           callback_data=f"part_{key}"))

    markup.row(
        ibtn(f"✅ Davom etish ({len(selected_parts)}/3)", YASHIL,
             callback_data="part_done")
    )

    return markup


# ================ MANBA KLAVIATURASI ================

# def source_inline_kb():
#     """Qayerdan keldi — inline"""
#     kb = InlineKeyboardMarkup(row_width=2)
#     kb.add(
#         ibtn("📱 Telegram",          KOK, callback_data="src_telegram"),
#         ibtn("📸 Instagram",         KOK, callback_data="src_instagram"),
#         ibtn("🤝 Do'st taklifi",     KOK, callback_data="src_referral"),
#         ibtn("🚶 O'zi keldi",        KOK, callback_data="src_walkin"),
#         ibtn("🔄 Avval ham kelgan",  KOK, callback_data="src_repeat"),
#         ibtn("🔹 Boshqa",            KOK, callback_data="src_other"),
#     )
#     return kb


# ================ BAHOLASH KLAVIATURALARI ================

# def rating_inline_kb(sale_id: int):
#     """Sotuvchini baholash — 1 dan 5 gacha raqamlar"""
#     kb = InlineKeyboardMarkup(row_width=5)
#     kb.row(*[
#         ibtn(str(i), KOK, callback_data=f"rate_{i}_{sale_id}")
#         for i in range(1, 6)
#     ])
#     kb.row(ibtn("⏭ O'tkazib yuborish", KOK, callback_data=f"rate_skip_{sale_id}"))
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
#         kb.insert(ibtn(label, KOK, callback_data=f"rsn_{key}_{sale_id}_{rating}"))
#     return kb


# ================ ADMIN KLAVIATURALARI ================

def admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, is_persistent=True)

    # Birinchi qator - Statistika va Ma'lumotlar
    kb.row(
        btn("📊 Statistika", KOK),
        btn("💳 Tariflar", KOK),
    )

    # Ikkinchi qator - Import va Export
    kb.row(
        btn("📥 Narxlarni import qilish", KOK),
        btn("📢 Reklama", KOK),
    )

    # Uchinchi qator - Foydalanuvchi boshqaruvi
    kb.row(
        btn("👤 Foydalanuvchi", KOK),
        btn("🛍 Mijoz xaridlari", KOK),
    )

    # To'rtinchi qator - Qo'shimcha funksiyalar.
    # "Narxlarni tozalash" QIZIL: u butun bazani o'chiradi va qo'shni
    # tugmalar bilan bir xil ko'rinsa, bexosdan bosilishi hech gap emas.
    kb.row(
        btn("📱 Namuna", KOK),
        btn("🗑 Narxlarni tozalash", QIZIL),
    )

    # Beshinchi qator - Rejimlar
    kb.row(
        btn("🔧 Tamirlash rejimi", KOK),
        btn("🆓 Bepul/Pullik rejim", KOK),
    )

    # Oltinchi qator - Hamma uchun urinish
    kb.row(btn("🎁 Hamma uchun urinish", KOK))

    # Yettinchi qator - Orqaga
    kb.row(btn("🏠 Bosh menyu", NAV))

    return kb


def maintenance_kb():
    """Tamirlash rejimi menu"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # Birinchi qator - Asosiy boshqaruv. Ranglar tugmaning o'z belgisiga
    # mos: yopish — qizil, ochish — yashil.
    kb.row(btn("🔴 Barchasini yopish", QIZIL))
    kb.row(btn("🟢 Barchasini ochish", YASHIL))

    # Ikkinchi qator - Bo'limlar
    kb.row(
        btn("📱 Narxlash", KOK),
        btn("💰 To'lov", KOK),
    )
    kb.row(
        btn("👤 Hisob", KOK),
        btn("📊 Holat", KOK),
    )

    # Uchinchi qator - Orqaga
    kb.row(btn("◀️ Orqaga", NAV))

    return kb


def cleanup_confirm_kb():
    """Bazani tozalash tasdiqlash"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    # Tasdiq ham QIZIL: bu yerda "ha" — qaytarib bo'lmaydigan tanlov,
    # yashil rang esa uni xavfsizdek ko'rsatib qo'yardi.
    kb.row(
        btn("✅ Ha, tozalash", QIZIL),
        btn("❌ Yo'q, bekor qilish", KOK),
    )
    kb.row(btn("🏠 Bosh menyu", NAV))
    return kb
