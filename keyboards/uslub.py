# keyboards/uslub.py — TUGMA RANGLARI (AIOGRAM 2.25.2)
#
# Telegram tugmalarga `style` maydonini qo'shish orqali rang beradi:
#
#   success  — YASHIL: asosiy harakat, odam shu tugma uchun kelgan
#   primary  — KO'K:   yordamchi yo'l / navigatsiya, foydali lekin majburiy emas
#   danger   — QIZIL:  bekor qilish, o'chirish, ortga qaytarib bo'lmaydigan tanlov
#
# DIQQAT: eski Telegram mijozlari `style` ni tanimaydi va tugmani odatdagidek
# (kulrang) chizadi. Shuning uchun rangga MA'NO YUKLAMASLIK kerak — rang faqat
# ko'zni yo'naltiradi, matnning o'rnini bosmaydi. Har bir tugmaning matni
# rangsiz ham tushunarli bo'lishi shart.
#
# aiogram 2 noma'lum maydonlarni `values` ga solib, JSON'ga o'zgarishsiz
# chiqaradi — shuning uchun kutubxonani yamashning hojati yo'q.

from aiogram.types import InlineKeyboardButton, KeyboardButton

__all__ = (
    "YASHIL", "KOK", "QIZIL", "ODDIY", "NAV",
    "rang", "btn", "ibtn",
)

YASHIL = "success"
KOK = "primary"
QIZIL = "danger"
ODDIY = ""  # rang umuman qo'shilmaydi

# NAVIGATSIYA — "◀️ Orqaga", "🏠 Bosh menyu" kabi tugmalar.
#
# Ular ataylab RANGSIZ. Telegram atigi uchta rang beradi va uchalasi ham
# band: yashil — asosiy harakat, ko'k — tanlov, qizil — xavfli amal.
# Navigatsiyani ham shulardan biriga bo'yash noto'g'ri bo'lardi: qizil
# "Orqaga" xavfli deb tushuniladi, ko'k esa uni tanlovlar bilan bir
# qatorga qo'yadi — xotira modeli 512 GB bilan "Orqaga" ni tenglashtiradi.
#
# Rangsiz tugma ko'zga urilmay, orqa fonga chekinadi. Ekrandagi TANLOV
# ajralib turadi, chiqish yo'li esa kerak bo'lganda topiladi. Farq ko'rinib
# turadi — aynan shu so'ralgandi.
NAV = ODDIY


# ─────────────────────────── AVTOMATIK RANG ───────────────────────────
#
# Tugmalar loyihada bir xil emoji bilan boshlanadi, shuning uchun rangni
# birinchi navbatda EMOJI aytib beradi: bitta joyda yozilgan qoida yuzlab
# tugmani bir xil ko'rinishga keltiradi va yangi tugma ham o'z-o'zidan
# to'g'ri rang oladi.

_EMOJI_RANG = {
    # navigatsiya — rangsiz (yuqoridagi NAV izohiga qarang)
    "◀️": NAV, "🏠": NAV, "⬅️": NAV, "🔙": NAV,
    # yashil — tasdiq, qo'shish, boshlash, pul kirimi
    "✅": YASHIL, "➕": YASHIL, "🟢": YASHIL, "▶️": YASHIL, "💳": YASHIL,
    "🎁": YASHIL, "💰": YASHIL, "📥": YASHIL,
    # qizil — rad, o'chirish, to'xtatish
    "❌": QIZIL, "⛔": QIZIL, "🚫": QIZIL, "🗑": QIZIL, "🔴": QIZIL,
    "➖": QIZIL, "⏸": QIZIL,
}

# So'zlar — emoji yordam bermaganda. Kichik harfda, matn ichidan qidiriladi.
_QIZIL_SOZ = (
    "bekor qilish", "yo'q", "to'xtatish", "tozalash", "o'chirish",
    "bloklash", "yopish", "chiqish",
)
_YASHIL_SOZ = (
    "ha,", "tasdiq", "yuborish", "davom", "boshlash", "saqlash",
    "to'ldirish", "qo'shish", "ochish", "to'lov qildim",
)


def rang(matn: str) -> str:
    """Tugma matniga qarab rang tanlaydi. Topolmasa — KO'K."""
    matn = (matn or "").strip()
    if not matn:
        return KOK

    # 1) Emoji prefiksi — eng ishonchli belgi.
    for emoji, uslub in _EMOJI_RANG.items():
        if matn.startswith(emoji):
            return uslub

    # 2) So'zlar. Qizil birinchi tekshiriladi: "Ha, tozalash" kabi
    #    aralash matnda xavfliroq ma'no ustun turishi kerak.
    past = matn.lower()
    for soz in _QIZIL_SOZ:
        if soz in past:
            return QIZIL
    for soz in _YASHIL_SOZ:
        if soz in past:
            return YASHIL

    # 3) Qolgani — ko'k: navigatsiya, ro'yxat, ma'lumot.
    return KOK


# ──────────────────────────── TUGMA YASASH ────────────────────────────
#
# `uslub=None` — rang matndan avtomatik aniqlanadi.
# `uslub=ODDIY` — rang UMUMAN qo'shilmaydi (kulrang qoladi).
#
# Bo'sh satr yuborish ham mumkin edi, lekin Telegram noma'lum/bo'sh
# qiymatga BUTUN xabarni rad etib javob beradi — ya'ni bitta e'tiborsizlik
# tufayli xabar umuman yetib bormasdi. Shuning uchun bo'sh uslub — maydon yo'q.


def btn(matn: str, uslub: str = None, **maydon) -> KeyboardButton:
    """Rangli oddiy (reply) tugma."""
    uslub = rang(matn) if uslub is None else uslub
    if uslub:
        maydon["style"] = uslub
    return KeyboardButton(matn, **maydon)


def ibtn(matn: str, uslub: str = None, **maydon) -> InlineKeyboardButton:
    """Rangli inline tugma."""
    uslub = rang(matn) if uslub is None else uslub
    if uslub:
        maydon["style"] = uslub
    return InlineKeyboardButton(matn, **maydon)
