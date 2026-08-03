# utils/emoji.py — ANIMATSION (CUSTOM) EMOJI
#
# Telegram'ning "premium emoji" lari xabar MATNIDA `<tg-emoji>` tegi orqali
# ishlatiladi. Botlar ularni Premium obunasiz yubora oladi va oluvchida ham
# Premium talab qilinmaydi — hamma animatsion ko'radi.
#
# QAYERDA ISHLAMAYDI: klaviatura tugmalarida. Tugma matni oddiy satr, unda
# HTML ham, entity ham yo'q — shuning uchun tugmalardagi emoji o'zgarishsiz
# qoladi (ular rang bilan ajratilgan, `keyboards/uslub.py` ga qarang).
#
# ID lar qayerdan olingan (`getStickerSet` orqali):
#   t.me/addemoji/RestrictedEmoji     — animatsion standart emoji (asosiy manba)
#   t.me/addemoji/IslomjonAnimeEmoji  — aralash animatsion
#   t.me/addemoji/NewsEmoji           — animatsion
#   t.me/addemoji/Decoration_Pack2    — video ikonkalar
#   t.me/addemoji/emojiuzbek          — video
#
# `tgiosicons` va `tgmacicons` ATAYLAB ishlatilmadi: ular monoxrom chiziqli
# ikonkalar va qorong'i fonda kulrang bo'lib qoladi — dastlab shulardan
# tanlangan edi, natija esa jonsiz chiqdi.
#
# ID lar TO'PLAMGA bog'liq emas: to'plam o'chib ketsa ham emoji ishlayveradi,
# chunki Telegram uni ID bo'yicha topadi.

import re

__all__ = ("CUSTOM_EMOJI", "bezash", "botga_ulash")

#: oddiy emoji -> custom_emoji_id
#:
#: Har biri QO'LDA, eskizlariga qarab tanlangan. Avtomatik tanlash yaramadi:
#: to'plam mualliflari emojini ixtiyoriy biriktiradi va "eng rangli" variant
#: 📱 uchun Xiaomi logotipini, 🔄 uchun "UPD" yozuvini, 📦 uchun Amazon
#: belgisini bergan edi. Rang muhim, lekin MA'NO undan muhimroq.
#:
#: Ko'pchiligi `RestrictedEmoji` dan — u standart emojilarning animatsion
#: nusxasi, ya'ni ma'nosi aniq va ko'rinishi tanish.
CUSTOM_EMOJI = {
    "❌": "5465665476971471368",   # RestrictedEmoji
    "✅": "5427009714745517609",   # RestrictedEmoji
    "🏠": "5465226866321268133",   # RestrictedEmoji
    "📱": "5407025283456835913",   # RestrictedEmoji
    "💰": "5375296873982604963",   # RestrictedEmoji
    "📊": "5431577498364158238",   # RestrictedEmoji
    "🎁": "5199749070830197566",   # RestrictedEmoji
    "⭐": "5435957248314579621",   # RestrictedEmoji
    "⚠️": "5188463524568926712",   # IslomjonAnimeEmoji
    "👥": "5372926953978341366",   # RestrictedEmoji
    "📞": "5343657129813221401",   # emojiuzbek
    "🔄": "5264727218734524899",   # RestrictedEmoji
    "👤": "5373012449597335010",   # RestrictedEmoji
    "⚡": "5431449001532594346",   # RestrictedEmoji
    "🔋": "5370715226209525171",   # IslomjonAnimeEmoji
    "🎨": "5431456208487716895",   # RestrictedEmoji
    "📈": "5244837092042750681",   # NewsEmoji
    "🚫": "5240241223632954241",   # NewsEmoji
    "🎉": "5436040291507247633",   # RestrictedEmoji
    "⬇️": "5314453632828055816",   # Decoration_Pack2
    "📲": "5406809207947142040",   # RestrictedEmoji
    "🏆": "5409008750893734809",   # RestrictedEmoji
    "⚙️": "5370935802844946281",   # IslomjonAnimeEmoji
    "📝": "5334882760735598374",   # RestrictedEmoji
    "🛡": "5251203410396458957",   # NewsEmoji
    "📣": "5469903029144657419",   # RestrictedEmoji
    "⛔": "5260293700088511294",   # NewsEmoji
    "🌍": "5399898266265475100",   # RestrictedEmoji
    "🔍": "5188217332748527444",   # RestrictedEmoji
    "⏳": "5451732530048802485",   # RestrictedEmoji

    # ── Qo'shimcha: botning boshqa xabarlarida uchraydiganlar ──
    "🛍": "5373052667671093676",   # RestrictedEmoji
    "📥": "5433811242135331842",   # RestrictedEmoji
    "📆": "5431897022456145283",   # RestrictedEmoji
    "➕": "5226945370684140473",   # RestrictedEmoji
    "➖": "5229113891081956317",   # RestrictedEmoji
    "🚀": "5445284980978621387",   # RestrictedEmoji
    "👋": "5472055112702629499",   # RestrictedEmoji
    "🙏": "5472189549473963781",   # RestrictedEmoji
    "💡": "5472146462362048818",   # RestrictedEmoji
    "🤝": "5357080225463149588",   # RestrictedEmoji
    "🥇": "5280735858926822987",   # RestrictedEmoji
    "🥈": "5283195573812340110",   # RestrictedEmoji
    "🥉": "5282750778409233531",   # RestrictedEmoji
    "🔗": "5375129357373165375",   # RestrictedEmoji
    "✏️": "5334673106202010226",   # RestrictedEmoji
    "📎": "5377844313575150051",   # RestrictedEmoji
    "✨": "5472164874886846699",   # RestrictedEmoji
    "🔎": "5188311512791393083",   # RestrictedEmoji
    "💼": "5359785904535774578",   # RestrictedEmoji
    "👇": "5470177992950946662",   # RestrictedEmoji
    "👑": "5467406098367521267",   # RestrictedEmoji
    "💥": "5469785308386041323",   # RestrictedEmoji
    "🔥": "5420315771991497307",   # RestrictedEmoji
    "🔐": "5472308992514464048",   # RestrictedEmoji
    "😤": "5370650883304462905",   # RestrictedEmoji
    "🔴": "5411225014148014586",   # NewsEmoji
    "🟢": "5416081784641168838",   # NewsEmoji
    "🗑": "5445267414562389170",   # NewsEmoji
    "📩": "5319185587276619437",   # Decoration_Pack2
    "💵": "5409048419211682843",   # NewsEmoji
    "ℹ️": "5334544901428229844",   # NewsEmoji
    "🗓": "5413879192267805083",   # NewsEmoji
    "🎧": "5316919120149619748",   # Decoration_Pack2
    "📌": "5397782960512444700",   # NewsEmoji
}

# ATAYLAB QO'SHILMAGANLAR.
#
# 📦 🗄️ 🌐 — to'plamlarda bor, lekin mazmuni boshqa: 📦 o'rniga Amazon
# logotipi, 🗄️ o'rniga "C" belgisi, 🌐 o'rniga ijtimoiy tarmoq
# nishonlari. Noto'g'ri rasmdan ko'ra oddiy emoji yaxshi.
#
# 💳 🔧 📢 📅 1️⃣ 2️⃣ 3️⃣ va boshqa raqamli emojilar — sakkiz to'plamning
# birortasida ham yo'q. Ular oddiy emoji bo'lib qolaveradi.

# Uzunroq kalit birinchi: "ℹ️" (variatsiya belgisi bilan) "ℹ" dan oldin
# tekshirilishi kerak, aks holda teg ichida ortiqcha belgi qolib ketardi.
_NAQSH = re.compile(
    "|".join(re.escape(e) for e in sorted(CUSTOM_EMOJI, key=len, reverse=True))
)

#: Bitta xabardagi eng ko'p almashtirish soni.
#:
#: Telegram bitta xabarda entity sonini cheklaydi va har bir teg matnni ~45
#: belgiga uzaytiradi — uzun statistika xabari 4096 belgilik chegaradan
#: oshib ketishi mumkin edi. Chegara ATAYLAB past: animatsion emoji ko'z
#: tortish uchun, xabarni bezash uchun emas.
STANDART_CHEGARA = 16

#: Telegram xabar matnining chegarasi va bitta tegning taxminiy uzunligi.
MAX_MATN = 4096
TEG_UZUNLIGI = 50


def bezash(matn: str, chegara: int = STANDART_CHEGARA) -> str:
    """
    Matndagi tanish emojilarni animatsion emojiga aylantiradi.

    `parse_mode="HTML"` bilan yuborilishi SHART — aks holda odam teglarni
    o'z ko'zi bilan o'qiydi.

    Ro'yxatda yo'q emoji (💳, 🔋, 💵, 🆔 kabi) o'z holicha qoladi: mos
    animatsion varianti topilmagan bo'lsa, oddiy emoji noto'g'risidan yaxshi.
    """
    if not matn or "<tg-emoji" in matn:
        # Ikki marta o'tkazilsa teg ichidagi emoji yana o'ralib, xabar
        # buzilardi. Bir marta bezalgan matn shundayligicha qaytadi.
        return matn

    # Har bir teg matnni ~45 belgiga uzaytiradi. Uzun xabar (masalan admin
    # statistikasi) 4096 belgilik chegaradan oshsa, Telegram uni BUTUNLAY
    # rad etadi — ya'ni bezak tufayli xabar umuman yetib bormasdi. Shuning
    # uchun avval joy hisoblanadi, keyin bezaladi.
    joy = (MAX_MATN - len(matn)) // TEG_UZUNLIGI
    chegara = min(chegara, max(joy, 0))
    if chegara <= 0:
        return matn

    qolgan = chegara

    def almashtir(m):
        nonlocal qolgan
        if qolgan <= 0:
            return m.group(0)
        qolgan -= 1
        e = m.group(0)
        return f'<tg-emoji emoji-id="{CUSTOM_EMOJI[e]}">{e}</tg-emoji>'

    return _NAQSH.sub(almashtir, matn)


# ─────────────────────────── BOTGA ULASH ───────────────────────────

#: Matn/izoh maydoni metodning nechanchi POZITSIYADA turishi (bog'langan
#: metodda `self` allaqachon berilgan, shuning uchun sanoq 0 dan).
_METODLAR = {
    "send_message": ("text", 1),
    "edit_message_text": ("text", 0),
    "send_photo": ("caption", None),
    "send_document": ("caption", None),
    "send_video": ("caption", None),
    "send_animation": ("caption", None),
    "edit_message_caption": ("caption", None),
}

_YOQ = object()


def _html_mi(bot, kwargs) -> bool:
    """
    Xabar HTML sifatida yuborilyaptimi.

    `parse_mode` berilmagan yoki `None` bo'lsa, aiogram botning standart
    rejimini qo'yadi (`loader.py` da HTML). Markdown bo'lsa bezamaymiz:
    u yerda `<tg-emoji>` tegi matn bo'lib ko'rinardi.
    """
    pm = kwargs.get("parse_mode", _YOQ)
    if pm is _YOQ or pm is None:
        pm = getattr(bot, "parse_mode", None)
    return isinstance(pm, str) and pm.lower() == "html"


def botga_ulash(bot) -> None:
    """
    Botning matn yuboradigan metodlarini bezak bilan o'raydi.

    NEGA SHU YERDA, HAR BIR HANDLERDA EMAS. Botda yuzdan ortiq
    `message.answer(...)` bor. Har biriga `bezash(...)` yozish — bir
    marta unutilsa, o'sha bitta xabar boshqalardan farq qilib turadigan
    ish. `Message.answer` esa oxir-oqibat `bot.send_message` ni chaqiradi,
    ya'ni bitta joyni o'rash hammasini qamrab oladi.

    Bezak faqat HTML rejimida va faqat tanish emojilarga tegadi; qolgan
    hamma narsa o'zgarishsiz o'tadi.
    """
    for nom, (maydon, orin) in _METODLAR.items():
        asl = getattr(bot, nom, None)
        if asl is None:
            continue
        setattr(bot, nom, _oral(bot, asl, maydon, orin))


def _oral(bot, asl, maydon, orin):
    async def yangi(*args, **kwargs):
        if _html_mi(bot, kwargs):
            if isinstance(kwargs.get(maydon), str):
                kwargs[maydon] = bezash(kwargs[maydon])
            elif orin is not None and len(args) > orin and isinstance(args[orin], str):
                args = list(args)
                args[orin] = bezash(args[orin])
                args = tuple(args)
        return await asl(*args, **kwargs)

    yangi.__name__ = getattr(asl, "__name__", "yangi")
    yangi.__doc__ = getattr(asl, "__doc__", None)
    return yangi
