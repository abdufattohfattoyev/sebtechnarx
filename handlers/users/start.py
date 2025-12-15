import traceback
import zipfile
import openpyxl
import pandas as pd
import sqlite3
import os
import re
import asyncio
import aiofiles
from datetime import datetime, timedelta

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, \
    ReplyKeyboardRemove
from aiogram.utils.exceptions import NetworkError, RetryAfter

from loader import dp, bot
from utils.db_api.database import (
    get_models, get_storages, get_colors, get_batteries,
    get_sim_types, get_price, get_conn, DB_PATH, normalize_damage_format
)
from utils.db_api.stats_database import (
    add_or_update_user, save_price_inquiry, register_user,
    is_user_registered, get_user_stats, get_global_stats,
    get_all_users, get_total_users, get_registered_users_count,
    get_active_users, get_total_price_inquiries
)
from data.config import ADMINS, START_PHOTO_FILE_ID

# ================ KONSTANTALAR ================

PARTS = {
    'battery': 'Batareyka',
    'back_cover': 'Krishka',
    'face_id': 'Face ID',
    'glass': 'Oyna',
    'screen': 'Ekran',
    'camera': 'Kamera',
    'broken': 'Qirilgan',
    'body': 'Korpus',
}

# Excel import uchun maksimal fayl hajmi (MB)
MAX_FILE_SIZE_MB = 31


# ================ HOLATLAR ================

class UserState(StatesGroup):
    waiting_phone = State()
    waiting_model = State()
    waiting_storage = State()
    waiting_color = State()
    waiting_battery = State()
    waiting_sim = State()
    waiting_box = State()
    waiting_parts_choice = State()
    waiting_parts = State()


class ImportState(StatesGroup):
    waiting_file = State()


class CleanupState(StatesGroup):
    confirm = State()


class ExportState(StatesGroup):
    waiting_format = State()


# ================ YANGILANGAN MENYULAR ================

def phone_request_kb():
    """Telefon raqam so'rash uchun klaviatura"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    return kb


def main_menu(is_admin=False):
    """Asosiy menyu - 2 qatordan"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # Birinchi qator - 2 ta tugma
    kb.row(
        KeyboardButton("📱 iPhone narxini bilish")
    )

    # Ikkinchi qator
    if is_admin:
        kb.row(
            KeyboardButton("🔧 Admin panel")
        )

    return kb


def back_kb():
    """Orqaga va Bosh menyu uchun klaviatura"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
    return kb


def admin_kb():
    """Admin paneli uchun klaviatura - 2 qatordan"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    # Birinchi qator - 2 ta tugma
    kb.row(
        KeyboardButton("📊 Statistika"),
        KeyboardButton("📥 Excel import")
    )

    # Ikkinchi qator - 2 ta tugma
    kb.row(
        KeyboardButton("📤 Excel export"),
        KeyboardButton("🧹 Bazani tozalash")
    )

    # Uchinchi qator - 2 ta tugma
    kb.row(
        KeyboardButton("📱 Namuna ma'lumot"),
        KeyboardButton("🏠 Bosh menyu")
    )

    return kb


def parts_choice_kb():
    """Almashgan qism bormi degan savol uchun klaviatura (oddiy keyboard)"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Ha"), KeyboardButton("❌ Yo'q"))
    kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
    return kb


def create_keyboard(items, row_width=2):
    """Dinamik klaviatura yaratish"""
    kb = ReplyKeyboardMarkup(resize_keyboard=True)

    for i in range(0, len(items), row_width):
        row_items = items[i:i + row_width]
        kb.row(*[KeyboardButton(item) for item in row_items])

    # Orqaga va Bosh menyu tugmalari
    kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
    return kb


# ================ BAZA FUNKSIYALARI ================

def get_total_prices_count():
    """Bazadagi jami narxlar soni"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM prices")
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0


def get_prices_for_model(model_id):
    """Model uchun narxlarni olish"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT * FROM prices
            WHERE model_id=?
            LIMIT 10
        """, (model_id,))
        rows = c.fetchall()
        conn.close()
        return rows
    except:
        return []


def clear_database():
    """Bazani tozalash (faqat narxlar va qismlar)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Faqat narxlar va qismlarni tozalash
        c.execute("DELETE FROM prices")
        c.execute("DELETE FROM parts")

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Bazani tozalashda xato: {e}")
        return False


def sort_models_naturally(models):
    """iPhone modellarini to'g'ri tartibda saralash (iPhone 11, 11 Pro, 11 Pro Max, ...)"""

    def extract_model_info(name):
        """Model nomidan raqam va turini ajratib olish"""
        name_lower = name.lower()

        # XS, XR, X modellar uchun maxsus tartib
        if 'xs max' in name_lower:
            return (10.5, 2)
        elif 'xs' in name_lower:
            return (10.5, 1)
        elif 'xr' in name_lower:
            return (10.3, 0)
        elif name_lower.endswith(' x'):
            return (10, 0)

        # Oddiy raqamli modellar
        match = re.search(r'iphone\s+(\d+)', name_lower)
        if match:
            number = int(match.group(1))

            # Pro Max, Pro, Mini, Plus kabi qo'shimchalarni aniqlash
            if 'pro max' in name_lower:
                priority = 3
            elif 'plus' in name_lower:
                priority = 3
            elif 'pro' in name_lower:
                priority = 2
            elif 'mini' in name_lower:
                priority = 1
            else:
                priority = 0

            return (number, priority)

        return (0, 0)

    return sorted(models, key=lambda x: extract_model_info(x['name']), reverse=True)


def sort_storages_naturally(storages):
    """Xotira hajmlarini to'g'ri tartibda saralash"""

    def extract_size(size_str):
        match = re.search(r'(\d+)', size_str)
        if match:
            return int(match.group(1))
        return 0

    return sorted(storages, key=lambda x: extract_size(x['size']), reverse=True)


def sort_batteries_naturally(batteries):
    """Batareyalarni to'g'ri tartibda saralash"""

    def extract_battery_percent(label):
        match = re.search(r'(\d+)', label)
        if match:
            return int(match.group(1))
        return 0

    return sorted(batteries, key=lambda x: extract_battery_percent(x['label']), reverse=True)


# ================ ASOSIY HANDLERLAR ================
ALLOWED_USERS = [
    1066769377, 85697724
]


# === START ===
@dp.message_handler(commands=['start'])
async def start(message: types.Message, state: FSMContext):
    user = message.from_user

    # ✅ Foydalanuvchini bazaga qo'shish (kontaktsiz)
    user_data = add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Ro'yxatdan o'tganligini tekshirish
    if not is_user_registered(user.id):
        text = f"""
👋 Assalomu alaykum, <b>{user.full_name}</b>!

📱 iPhone narxlarini aniq hisoblaymiz

<b>⬇️ Davom etish uchun telefon raqamingizni yuboring:</b>
"""
        await message.answer(
            text,
            reply_markup=phone_request_kb(),
            parse_mode="HTML"
        )
        await UserState.waiting_phone.set()
    else:
        await state.finish()
        models = get_models()
        text = f"""
👋 Assalomu alaykum, <b>{user.full_name}</b>!

📱 iPhone narxlarini aniq hisoblaymiz
✅ Hozir <b>{len(models)}</b> ta model mavjud

<b>⬇️ Quyidagi menyulardan birini tanlang:</b>
"""
        await message.answer(text, reply_markup=main_menu(user.id in ADMINS), parse_mode="HTML")


# === TELEFON RAQAM QABUL QILISH ===
@dp.message_handler(content_types=['contact'], state=UserState.waiting_phone)
async def process_phone(message: types.Message, state: FSMContext):
    user = message.from_user
    phone = message.contact.phone_number

    # Telefon raqam bilan ro'yxatdan o'tkazish
    register_user(user_id=user.id, phone_number=phone)

    models = get_models()
    text = f"""\
👋 Assalomu alaykum, <b>{user.full_name}</b>!

📱 iPhone narxlarini aniq hisoblaymiz
✅ Hozir <b>{len(models)}</b> ta model mavjud

<b>⬇️ Quyidagi menyulardan birini tanlang:</b>
"""
    await message.answer(text, reply_markup=main_menu(user.id in ADMINS), parse_mode="HTML")
    await state.finish()


# === MODEL TANLASH ===
@dp.message_handler(lambda m: m.text == "📱 iPhone narxini bilish")
async def choose_model(message: types.Message, state: FSMContext):
    # Foydalanuvchi ro'yxatdan o'tganligini tekshirish
    if not is_user_registered(message.from_user.id):
        text = f"""\
📱 iPhone narxini bilish uchun avval ro'yxatdan o'tishingiz kerak.

<b>⬇️ Telefon raqamingizni yuboring:</b>
"""
        await message.answer(
            text,
            reply_markup=phone_request_kb(),
            parse_mode="HTML"
        )
        await UserState.waiting_phone.set()
        return

    models = get_models()
    if not models:
        await message.answer("❌ Hozircha modellar mavjud emas", reply_markup=main_menu())
        return

    # Modellarni tartibga solish
    sorted_models = sort_models_naturally(models)

    # Model nomlarini olish
    model_names = [m['name'] for m in sorted_models]

    # Klaviatura yaratish (qatorda 2 ta tugma)
    kb = create_keyboard(model_names, row_width=2)

    await message.answer("<b>📱 Modelni tanlang:</b>", reply_markup=kb, parse_mode="HTML")
    await UserState.waiting_model.set()


@dp.message_handler(state=UserState.waiting_model)
async def model_selected(message: types.Message, state: FSMContext):
    if message.text in ["🏠 Bosh menyu", "◀️ Orqaga"]:
        await state.finish()
        await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    model = next((m for m in get_models() if m['name'] == message.text), None)
    if not model:
        await message.answer("❌ Model topilmadi, qayta tanlang")
        return

    await state.update_data(model_id=model['id'], model_name=model['name'])
    storages = get_storages(model['id'])

    if not storages:
        await message.answer("❌ Bu model uchun xotira variantlari mavjud emas", reply_markup=main_menu())
        await state.finish()
        return

    # Xotiralarni tartibga solish
    sorted_storages = sort_storages_naturally(storages)

    # Xotira variantlarini olish
    storage_sizes = [s['size'] for s in sorted_storages]

    # Klaviatura yaratish (qatorda 3 ta tugma)
    kb = create_keyboard(storage_sizes, row_width=3)

    await message.answer("<b>💾 Xotira hajmini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
    await UserState.waiting_storage.set()


# === ORQAGA ===
@dp.message_handler(lambda m: m.text in ["◀️ Orqaga", "🏠 Bosh menyu"], state="*")
async def back_handler(message: types.Message, state: FSMContext):
    current = await state.get_state()

    if not current:
        await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    if message.text == "🏠 Bosh menyu":
        await state.finish()
        await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    # Orqaga bosilganda oldingi bosqichga qaytish
    if current == UserState.waiting_storage.state:
        await choose_model(message, state)

    elif current == UserState.waiting_color.state:
        # Model tanlangan edi, xotira tanlashga qaytish
        data = await state.get_data()
        storages = get_storages(data['model_id'])

        if not storages:
            await state.finish()
            await message.answer("❌ Xotira variantlari yo'q", reply_markup=main_menu(message.from_user.id in ADMINS))
            return

        sorted_storages = sort_storages_naturally(storages)
        storage_sizes = [s['size'] for s in sorted_storages]
        kb = create_keyboard(storage_sizes, row_width=3)

        await message.answer("<b>💾 Xotira hajmini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_storage.set()

    elif current == UserState.waiting_battery.state:
        # Rang tanlashga qaytish
        data = await state.get_data()
        colors = get_colors(data['model_id']) or [{"name": "Standart"}]
        color_names = [c['name'] for c in colors]
        kb = create_keyboard(color_names, row_width=2)

        await message.answer("<b>🎨 Rangni tanlang:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_color.set()

    elif current == UserState.waiting_sim.state:
        # Batareya tanlashga qaytish
        data = await state.get_data()
        batteries = get_batteries(data['model_id']) or [{"label": "100%"}]
        sorted_batteries = sort_batteries_naturally(batteries)
        battery_labels = [b['label'] for b in sorted_batteries]
        kb = create_keyboard(battery_labels, row_width=2)

        await message.answer("<b>🔋 Batareya holatini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_battery.set()

    elif current == UserState.waiting_box.state:
        # SIM yoki batareyaga qaytish
        data = await state.get_data()
        sims = get_sim_types(data['model_id'])

        if len(sims) == 1:
            # Agar 1 ta SIM bo'lsa, batareyaga qaytish
            batteries = get_batteries(data['model_id']) or [{"label": "100%"}]
            sorted_batteries = sort_batteries_naturally(batteries)
            battery_labels = [b['label'] for b in sorted_batteries]
            kb = create_keyboard(battery_labels, row_width=2)

            await message.answer("<b>🔋 Batareya holatini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
            await UserState.waiting_battery.set()
        else:
            # SIM tanlashga qaytish
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row(KeyboardButton("📱 SIM karta"), KeyboardButton("📲 eSIM"))
            kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))

            await message.answer("<b>📞 SIM turini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
            await UserState.waiting_sim.set()

    elif current == UserState.waiting_parts_choice.state:
        # Quti tanlashga qaytish
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("✅ Bor"), KeyboardButton("❌ Yo'q"))
        kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))

        await message.answer("<b>📦 Quti bor/yo'q:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_box.set()

    elif current == UserState.waiting_parts.state:
        # Qismlar tanloviga qaytish
        await state.update_data(selected_parts=[])

        await message.answer(
            "<b>🔧 Telefonning qismlari almashganmi?</b>",
            reply_markup=parts_choice_kb(),
            parse_mode="HTML"
        )
        await UserState.waiting_parts_choice.set()


# === QOLGAN BOSQICHLAR ===
@dp.message_handler(state=UserState.waiting_storage)
async def storage_selected(message: types.Message, state: FSMContext):
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        return await back_handler(message, state)

    await state.update_data(storage=message.text)
    data = await state.get_data()
    colors = get_colors(data['model_id']) or [{"name": "Standart"}]

    color_names = [c['name'] for c in colors]
    kb = create_keyboard(color_names, row_width=2)

    await message.answer("<b>🎨 Rangni tanlang:</b>", reply_markup=kb, parse_mode="HTML")
    await UserState.waiting_color.set()


@dp.message_handler(state=UserState.waiting_color)
async def color_selected(message: types.Message, state: FSMContext):
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        return await back_handler(message, state)

    await state.update_data(color=message.text if message.text != "Standart" else "")
    data = await state.get_data()
    batteries = get_batteries(data['model_id']) or [{"label": "100%"}]

    # Batareyalarni tartibga solish
    sorted_batteries = sort_batteries_naturally(batteries)

    # Batareya yorliqlarini olish
    battery_labels = [b['label'] for b in sorted_batteries]

    # Klaviatura yaratish (qatorda 2 ta tugma)
    kb = create_keyboard(battery_labels, row_width=2)

    await message.answer("<b>🔋 Batareya holatini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
    await UserState.waiting_battery.set()


@dp.message_handler(state=UserState.waiting_battery)
async def battery_selected(message: types.Message, state: FSMContext):
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        return await back_handler(message, state)

    await state.update_data(battery=message.text)
    data = await state.get_data()
    sims = get_sim_types(data['model_id'])

    if len(sims) == 1:
        await state.update_data(sim_type=sims[0]['type'])

        # Quti bor/yo'q uchun klaviatura (2 qatordan)
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("✅ Bor"), KeyboardButton("❌ Yo'q"))
        kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))

        await message.answer("<b>📦 Quti bor/yo'q:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_box.set()
    else:
        # SIM turi uchun klaviatura (2 qatordan)
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("📱 SIM karta"), KeyboardButton("📲 eSIM"))
        kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))

        await message.answer("<b>📞 SIM turini tanlang:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_sim.set()


@dp.message_handler(state=UserState.waiting_sim)
async def sim_selected(message: types.Message, state: FSMContext):
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        return await back_handler(message, state)

    sim_type = "esim" if "eSIM" in message.text else "physical"
    await state.update_data(sim_type=sim_type)

    # Quti bor/yo'q uchun klaviatura (2 qatordan)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Bor"), KeyboardButton("❌ Yo'q"))
    kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))

    await message.answer("<b>📦 Quti bor/yo'q:</b>", reply_markup=kb, parse_mode="HTML")
    await UserState.waiting_box.set()


@dp.message_handler(state=UserState.waiting_box)
async def box_selected(message: types.Message, state: FSMContext):
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        return await back_handler(message, state)

    has_box = "Bor" if "Bor" in message.text else "Yo'q"
    await state.update_data(has_box=has_box)

    # Almashgan qism bormi degan savol (oddiy keyboard)
    await message.answer(
        "<b>🔧 Telefonning qismlari almashganmi?</b>",
        reply_markup=parts_choice_kb(),
        parse_mode="HTML"
    )
    await UserState.waiting_parts_choice.set()


@dp.message_handler(state=UserState.waiting_parts_choice)
async def parts_choice_selected(message: types.Message, state: FSMContext):
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        return await back_handler(message, state)

    if message.text == "❌ Yo'q":
        # Almashgan qism yo'q - Yangi telefon
        await state.update_data(selected_parts=[], damage_display="Yangi")
        await show_final_price(message, state)
        return

    if message.text == "✅ Ha":
        # Ha bosildi - Inline qismlar tanlovini ko'rsatish (2 tadan)
        markup = InlineKeyboardMarkup(row_width=2)
        for key, name in PARTS.items():
            markup.insert(InlineKeyboardButton(f"☐ {name}", callback_data=f"part_{key}"))
        markup.row(InlineKeyboardButton("✅ Davom etish", callback_data="part_done"))

        # Faqat Orqaga va Bosh menyu qolsin
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))

        await message.answer(
            "<b>🔧 Almashgan qismlarni tanlang (maks 3 ta):</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )

        # Inline klaviaturani alohida xabarda yuborish
        await message.answer(
            "⬇️ Quyidagi qismlardan tanlang:",
            reply_markup=markup
        )

        await UserState.waiting_parts.set()
        return

    # Noto'g'ri javob
    await message.answer(
        "❌ Iltimos, tugmalardan birini tanlang:",
        reply_markup=parts_choice_kb()
    )


# === INLINE CALLBACK - QISMLAR TANLASH ===
@dp.callback_query_handler(state=UserState.waiting_parts)
async def parts_callback(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get('selected_parts', [])

    if call.data == "part_done":
        if not selected:
            await call.answer("❌ Hech narsa tanlanmadi!", show_alert=True)
            return

        # Tanlangan qismlarni saqlash
        damage_display = " + ".join([PARTS[k] for k in sorted(selected)])
        await state.update_data(damage_display=damage_display)

        # Inline xabarlarni o'chirish
        try:
            await call.message.delete()
        except:
            pass

        # To'g'ridan-to'g'ri yakuniy narxni ko'rsatish
        await show_final_price(call.message, state)
        await call.answer()
        return

    part_key = call.data.replace("part_", "")

    # Ekran + Oyna bloklash
    if part_key in ("screen", "glass"):
        other = "glass" if part_key == "screen" else "screen"
        if other in selected:
            await call.answer("❌ Ekran va Oyna birga bo'lishi mumkin emas!", show_alert=True)
            return

    # Tanlash/o'chirish
    if part_key in selected:
        selected.remove(part_key)
    else:
        if len(selected) >= 3:
            await call.answer("❌ Maksimum 3 ta qism tanlash mumkin!", show_alert=True)
            return
        selected.append(part_key)

    await state.update_data(selected_parts=selected)

    # Yangi klaviatura (2 tadan)
    markup = InlineKeyboardMarkup(row_width=2)
    for key, name in PARTS.items():
        text = f"{'✅' if key in selected else '☐'} {name}"
        markup.insert(InlineKeyboardButton(text, callback_data=f"part_{key}"))
    markup.row(InlineKeyboardButton(f"✅ Davom etish ({len(selected)}/3)", callback_data="part_done"))

    # Tanlangan qismlar sonini ko'rsatish
    selected_names = [PARTS[k] for k in sorted(selected)]
    if selected_names:
        text = f"<b>🔧 Tanlangan:</b> {', '.join(selected_names)}"
    else:
        text = "<b>🔧 Almashgan qismlarni tanlang (maks 3 ta):</b>"

    try:
        await call.message.edit_text(
            text,
            reply_markup=markup,
            parse_mode="HTML"
        )
    except:
        pass

    await call.answer()


# === YAKUNIY NARX ===
from datetime import datetime

async def show_final_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get('selected_parts', [])
    color = data.get('color') or ""

    if not selected:
        damage_pct = "Yangi"
        damage_display = "Ideal"
    else:
        damage_pct = "+".join(sorted(selected))
        damage_display = data.get(
            'damage_display',
            " + ".join([PARTS[k] for k in sorted(selected)])
        )

    # Narx olish
    price = get_price(
        model_id=data['model_id'],
        storage=data['storage'],
        color=color,
        sim_type=data['sim_type'],
        battery=data['battery'],
        has_box=data['has_box'],
        damage=damage_pct
    )

    # Sana va vaqt
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    # Statistika
    if price:
        save_price_inquiry(
            user_id=message.from_user.id,
            model_name=data['model_name'],
            storage=data['storage'],
            color=color,
            sim=data['sim_type'],
            battery=data['battery'],
            box=data['has_box'],
            damage=damage_display,
            price=str(price)
        )

    # Narxni formatlash
    if price:
        if float(price).is_integer():
            price_text = f"{float(price):,.0f} $"
        else:
            price_text = f"{float(price):,.2f} $"
    else:
        price_text = "❌ Topilmadi"

    # Yakuniy xabar
    text = f"""\
📊 <b>HISOBLASH NATIJASI</b>

📱 <b>Model:</b> {data['model_name']}
💾 <b>Xotira:</b> {data['storage']}
🎨 <b>Rang:</b> {color or 'Standart'}
📞 <b>SIM:</b> {'📲 eSIM' if data['sim_type'] == 'esim' else '📱 SIM karta'}
🔋 <b>Batareya:</b> {data['battery']}
📦 <b>Quti:</b> {'✅ Bor' if data['has_box'] == 'Bor' else '❌ Yo‘q'}
🔧 <b>Holat:</b> {damage_display}

💰 {price_text}

🕒 <b>Hisoblangan vaqt:</b> {now}
    """.strip()

    # Tugmalar
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("🔄 Yana hisoblash"),
        KeyboardButton("🏠 Bosh menyu")
    )

    await message.answer(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await state.finish()



# === YANA HISOBLASH ===
@dp.message_handler(lambda m: m.text == "🔄 Yana hisoblash")
async def again(message: types.Message, state: FSMContext):
    await choose_model(message, state)



# ================ ADMIN FUNKSIYALARI ================

# === ADMIN PANEL ===
@dp.message_handler(lambda m: m.text == "🔧 Admin panel" and m.from_user.id in ADMINS)
async def admin_panel(message: types.Message):
    models_count = len(get_models())
    prices_count = get_total_prices_count()

    text = f"""\
<b>👨‍💼 ADMIN PANEL</b>

📊 <b>Statistika:</b>
- 📱 Modellar: {models_count} ta
- 💰 Narxlar: {prices_count} ta
- 👥 Adminlar: {len(ADMINS)} ta

<b>🔧 Mavjud amallar:</b>
1. 📥 Excel import - Django dan export qilingan faylni yuklash
2. 📤 Excel export - Bazadagi narxlarni Excel ga yuklash
3. 📊 Statistika - To'liq statistika
4. 🧹 Tozalash - Test ma'lumotlarni o'chirish
5. 📱 Namuna - Bir model uchun narxlarni ko'rish

<b>⚠️ Diqqat:</b> Import qilishdan oldin eski faylni yuklab oling!
    """

    await message.answer(text, reply_markup=admin_kb(), parse_mode="HTML")


# === STATISTIKA === (start.py dagi 📊 Statistika handlerini almashtiring)

@dp.message_handler(lambda m: m.text == "📊 Statistika" and m.from_user.id in ADMINS)
async def admin_statistics(message: types.Message):
    try:
        progress_msg = await message.answer("⏳ Statistika tayyorlanmoqda...")

        # 1. Asosiy raqamlar
        try:
            models_count = len(get_models())
        except:
            models_count = 0

        try:
            prices_count = get_total_prices_count()
        except:
            prices_count = 0

        try:
            total_users = get_total_users()
        except Exception as e:
            print(f"total_users xato: {e}")
            total_users = 0

        try:
            registered_users = get_registered_users_count()
        except Exception as e:
            print(f"registered_users xato: {e}")
            registered_users = 0

        try:
            active_users_today = get_active_users(1)
        except Exception as e:
            print(f"active_users_today xato: {e}")
            active_users_today = 0

        try:
            active_users_week = get_active_users(7)
        except Exception as e:
            print(f"active_users_week xato: {e}")
            active_users_week = 0

        try:
            active_users_month = get_active_users(30)
        except Exception as e:
            print(f"active_users_month xato: {e}")
            active_users_month = 0

        # 2. Global statistika
        try:
            today_stats = get_global_stats('today')
        except Exception as e:
            print(f"today_stats xato: {e}")
            today_stats = {'total_inquiries': 0, 'active_users': 0, 'unique_models': 0}

        try:
            week_stats = get_global_stats('week')
        except Exception as e:
            print(f"week_stats xato: {e}")
            week_stats = {'total_inquiries': 0, 'active_users': 0, 'unique_models': 0}

        try:
            month_stats = get_global_stats('month')
        except Exception as e:
            print(f"month_stats xato: {e}")
            month_stats = {'total_inquiries': 0, 'active_users': 0, 'unique_models': 0}

        try:
            all_stats = get_global_stats('all')
        except Exception as e:
            print(f"all_stats xato: {e}")
            all_stats = {'total_inquiries': 0, 'top_models': [], 'top_users': []}

        # 3. Jami narxlatishlar (price_history jadvalidan)
        try:
            total_price_inquiries = get_total_price_inquiries()
        except:
            total_price_inquiries = 0

        text = f"""<b>📊 ADMIN STATISTIKA</b>

<b>👥 FOYDALANUVCHILAR:</b>
• Jami: <b>{total_users}</b> ta
• Ro'yxatdan o'tgan: <b>{registered_users}</b> ta
• Faol (bugun): <b>{active_users_today}</b> ta
• Faol (hafta): <b>{active_users_week}</b> ta
• Faol (oy): <b>{active_users_month}</b> ta

<b>📈 NARXLATISH STATISTIKASI:</b>
• Bugungi: <b>{today_stats.get('total_inquiries', 0)}</b> ta
• Haftalik: <b>{week_stats.get('total_inquiries', 0)}</b> ta
• Oylik: <b>{month_stats.get('total_inquiries', 0)}</b> ta
• Jami: <b>{total_price_inquiries}</b> ta

<b>📱 MODELLAR VA NARXLAR:</b>
• Modellar: <b>{models_count}</b> ta
• Narxlar (bazada): <b>{prices_count}</b> ta
"""

        # 4. TOP 3 modellar
        top_models = all_stats.get('top_models', [])[:3]
        if top_models:
            text += f"\n<b>🏆 ENG KO'P NARXLATILGAN (TOP 3):</b>\n"
            for i, model in enumerate(top_models, 1):
                model_name = model.get('model_name', 'Noma\'lum')
                count = model.get('count', 0)
                text += f"{i}. {model_name}: <b>{count}</b> marta\n"
        else:
            text += "\n<b>🏆 ENG KO'P NARXLATILGAN:</b>\nHali ma'lumot yo'q\n"

        # 5. Bugungi TOP 3 foydalanuvchilar
        today_top_users = today_stats.get('top_users', [])[:3] if today_stats else []
        if today_top_users:
            text += f"\n<b>⭐ BUGUNGI FAOL (TOP 3):</b>\n"
            for i, user in enumerate(today_top_users, 1):
                username = user.get('username') or user.get('first_name', 'Foydalanuvchi')
                count = user.get('count', 0)
                # Username bo'lsa @ bilan, aks holda ismni ko'rsat
                display_name = f"@{username}" if user.get('username') else username
                text += f"{i}. {display_name}: <b>{count}</b> marta\n"

        # 6. Haftalik umumiy statistika
        text += f"\n<b>📅 HAFTALIK STATISTIKA:</b>\n"
        text += f"• Faol foydalanuvchilar: <b>{week_stats.get('active_users', 0)}</b> ta\n"
        text += f"• Narxlar soni: <b>{week_stats.get('total_inquiries', 0)}</b> ta\n"
        text += f"• Faol modellar: <b>{week_stats.get('unique_models', 0)}</b> ta\n"

        # 7. Vaqt markeri
        now = datetime.now()
        text += f"\n<b>🕐 Yangilangan:</b> {now.strftime('%d.%m.%Y %H:%M')}"

        await progress_msg.edit_text(text, parse_mode="HTML")

    except Exception as e:
        error_text = f"❌ Statistika olishda xato:\n<code>{str(e)[:300]}</code>"
        try:
            await message.answer(error_text, parse_mode="HTML")
        except:
            await message.answer(f"❌ Statistika olishda xato: {str(e)[:100]}")

        traceback.print_exc()


# === EXCEL IMPORT ===
@dp.message_handler(lambda m: m.text == "📥 Excel import" and m.from_user.id in ADMINS)
async def import_start(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("❌ Bekor qilish"), KeyboardButton("🏠 Bosh menyu"))

    await message.answer(
        "<b>📥 Excel faylni yuboring</b> (.xlsx yoki .xls)\n\n"
        "⚠️ <b>Fayl talablari:</b>\n"
        "• Format: Excel (.xlsx, .xls)\n"
        "• Hajm: maksimal 20 MB\n"
        "• Ustunlar (kamida): Model, Xotira, Narx\n\n"
        "📊 <b>Ixtiyoriy ustunlar:</b>\n"
        "• Rang, SIM, Batareya, Quti, Qismlar\n\n"
        "<i>Faylni jo'natish uchun 📎 tugmasini bosing</i>",
        reply_markup=kb, parse_mode="HTML"
    )
    await ImportState.waiting_file.set()


@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state=ImportState.waiting_file)
async def cancel_import(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("✅ Import bekor qilindi", reply_markup=admin_kb())


async def safe_edit_message(progress_msg, text, parse_mode="HTML", max_retries=3):
    """Flood control bilan kurashish uchun xavfsiz edit_message funksiyasi"""
    for retry in range(max_retries):
        try:
            await progress_msg.edit_text(text, parse_mode=parse_mode)
            return True
        except RetryAfter as e:
            wait_time = e.timeout + 1
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"Xatolik yuborishda: {e}")
            if retry == max_retries - 1:
                return False
    return False


async def safe_send_message(bot_or_message, chat_id=None, text=None, parse_mode="HTML", **kwargs):
    """Flood control bilan kurashish uchun xavfsiz send_message funksiyasi"""
    max_retries = 3
    for retry in range(max_retries):
        try:
            if isinstance(bot_or_message, types.Message):
                return await bot_or_message.answer(text, parse_mode=parse_mode, **kwargs)
            else:
                return await bot_or_message.send_message(chat_id, text, parse_mode=parse_mode, **kwargs)
        except RetryAfter as e:
            wait_time = e.timeout + 1
            await asyncio.sleep(wait_time)
        except Exception as e:
            print(f"Xatolik yuborishda: {e}")
            if retry == max_retries - 1:
                return None
    return None


def optimize_database_for_import():
    """Import uchun bazani optimallashtirish"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA synchronous = NORMAL")
    c.execute("PRAGMA cache_size = 10000")
    c.execute("PRAGMA foreign_keys = OFF")

    conn.commit()
    return conn


def restore_database_settings(conn):
    """Bazani normal holatiga qaytarish"""
    try:
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA synchronous = FULL")
        conn.commit()
    except:
        pass


@dp.message_handler(content_types=['document'], state=ImportState.waiting_file)
async def process_import(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await safe_send_message(message, text="🚫 Ruxsat yo'q")
        await state.finish()
        return

    progress_msg = await safe_send_message(message, text="⏳ Fayl yuklanmoqda...")
    if not progress_msg:
        await state.finish()
        return

    timestamp = int(datetime.now().timestamp())
    file_path = f"temp_import_{user_id}_{timestamp}.xlsx"

    try:
        # ✅ 1. TIMEOUT BILAN YUKLASH
        try:
            file = await asyncio.wait_for(
                bot.get_file(message.document.file_id),
                timeout=30
            )
            await asyncio.wait_for(
                bot.download_file(file.file_path, file_path),
                timeout=90
            )
        except asyncio.TimeoutError:
            await safe_edit_message(
                progress_msg,
                "❌ Fayl yuklash timeout.\n\n"
                "Iltimos, qayta urinib ko'ring yoki faylni kichikroq qiling."
            )
            await state.finish()
            return
        except Exception as download_error:
            error_text = str(download_error)

            if "too big" in error_text.lower() or "too large" in error_text.lower():
                try:
                    file_size_mb = message.document.file_size / (1024 * 1024)
                except:
                    file_size_mb = 0

                await safe_edit_message(
                    progress_msg,
                    f"❌ <b>Fayl juda katta!</b>\n\n"
                    f"📁 Telegram Bot API limiti: 20 MB\n"
                    f"{'📊 Sizning fayl: ' + f'{file_size_mb:.1f} MB' if file_size_mb > 0 else ''}\n\n"
                    f"💡 <b>Yechim:</b>\n"
                    f"1️⃣ Excel faylni 2-3 qismga bo'ling\n"
                    f"2️⃣ Har bir qismni alohida import qiling\n"
                    f"3️⃣ Ma'lumotlarni kamroq qiling\n\n"
                    f"<b>📝 Qanday bo'lish:</b>\n"
                    f"• Excel ni oching\n"
                    f"• 1-30,000 qatorni tanlang → Save As → qism1.xlsx\n"
                    f"• 30,001-60,000 → qism2.xlsx\n"
                    f"• Har birini alohida import qiling"
                )
            else:
                await safe_edit_message(
                    progress_msg,
                    f"❌ Faylni yuklab bo'lmadi:\n<code>{error_text[:200]}</code>\n\n"
                    f"Iltimos, qayta urinib ko'ring."
                )

            await state.finish()
            return

        # 2. Yuklangan faylni tekshirish
        if not os.path.exists(file_path):
            await safe_edit_message(progress_msg, "❌ Fayl yuklanmadi, qayta urinib ko'ring")
            await state.finish()
            return

        # 3. Haqiqiy hajmni tekshirish
        actual_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        if actual_size_mb > MAX_FILE_SIZE_MB:
            await safe_edit_message(
                progress_msg,
                f"❌ <b>Fayl juda katta: {actual_size_mb:.1f} MB</b>\n\n"
                f"📁 Maksimal: {MAX_FILE_SIZE_MB} MB\n\n"
                f"💡 Faylni kichikroq qismlarga bo'ling va alohida import qiling."
            )
            os.remove(file_path)
            await state.finish()
            return

        await safe_edit_message(
            progress_msg,
            f"✅ Fayl yuklandi: {actual_size_mb:.1f} MB\n📊 Ma'lumotlar tahlil qilinmoqda..."
        )

        # ✅ 4. MEMORY-EFFICIENT EXCEL O'QISH
        try:
            df = pd.read_excel(file_path, dtype=str, engine='openpyxl')
        except Exception as e:
            try:
                df = pd.read_excel(file_path, dtype=str, engine='xlrd')
            except Exception as e2:
                await safe_edit_message(
                    progress_msg,
                    f"❌ Excel faylni ochib bo'lmadi:\n<code>{str(e)[:100]}</code>\n\n"
                    f"Yoki:\n<code>{str(e2)[:100]}</code>\n\n"
                    f"Fayl buzilgan bo'lishi mumkin."
                )
                os.remove(file_path)
                await state.finish()
                return

        # 5. Ma'lumotlarni tozalash
        df = df.fillna('')
        df.columns = [str(col).strip() for col in df.columns]

        # Ustun nomlarini standartlashtirish
        column_mapping = {
            'Model': ['model', 'модель', 'iphone'],
            'Xotira': ['xotira', 'storage', 'size', 'память', 'объем'],
            'Rang': ['rang', 'color', 'цвет', 'colour'],
            'SIM': ['sim', 'сим', 'esim'],
            'Batareya': ['batareya', 'battery', 'батарея', 'аккумулятор'],
            'Quti': ['quti', 'box', 'кути', 'коробка', 'упаковка'],
            'Qismlar': ['qismlar', 'parts', 'damage', 'holat', 'состояние', 'дефекты', 'kombinatsiya'],
            'Narx': ['narx', 'price', 'цена', 'стоимость', 'narx ($)']
        }

        for col in df.columns:
            col_lower = col.lower()
            for std_name, variants in column_mapping.items():
                if any(variant in col_lower for variant in variants):
                    df.rename(columns={col: std_name}, inplace=True)
                    break

        # 6. Kerakli ustunlarni tekshirish
        required_columns = ['Model', 'Narx']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            available_cols = ', '.join(df.columns.tolist())
            await safe_edit_message(
                progress_msg,
                f"❌ Kerakli ustunlar topilmadi: {', '.join(missing_columns)}\n\n"
                f"📋 Mavjud ustunlar: {available_cols}"
            )
            os.remove(file_path)
            await state.finish()
            return

        total_rows = len(df)

        # ✅ Juda katta fayl ogohlantirish
        if total_rows > 50000:
            await safe_edit_message(
                progress_msg,
                f"⚠️ Juda ko'p qator: {total_rows:,}\n\n"
                f"Import 5-10 daqiqa davom etishi mumkin.\n"
                f"Iltimos sabr bilan kuting..."
            )
            await asyncio.sleep(2)

        await safe_edit_message(
            progress_msg,
            f"✅ {total_rows:,} ta ma'lumot topildi\n🔄 Bazaga yozilmoqda... (0/{total_rows:,})"
        )

        # ✅ 7. OPTIMALLASHTIRILGAN BAZA ULANISH
        conn = optimize_database_for_import()
        c = conn.cursor()

        # ✅ Xotira optimizatsiyasi
        c.execute("PRAGMA temp_store = MEMORY")
        c.execute("PRAGMA mmap_size = 30000000000")
        c.execute("PRAGMA page_size = 4096")

        conn.execute("BEGIN TRANSACTION")

        # Jadvallarni yaratish
        c.execute('''CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            default_sim_type TEXT DEFAULT 'physical',
            base_standard_price REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS storages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            size TEXT,
            price_difference REAL DEFAULT 0,
            is_standard BOOLEAN DEFAULT 0,
            UNIQUE(model_id, size),
            FOREIGN KEY (model_id) REFERENCES models (id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            name TEXT,
            price_difference REAL DEFAULT 0,
            color_type TEXT DEFAULT 'standard',
            UNIQUE(model_id, name),
            FOREIGN KEY (model_id) REFERENCES models (id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS batteries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            label TEXT,
            min_percent INTEGER DEFAULT 100,
            max_percent INTEGER DEFAULT 100,
            price_difference REAL DEFAULT 0,
            is_standard BOOLEAN DEFAULT 1,
            UNIQUE(model_id, label),
            FOREIGN KEY (model_id) REFERENCES models (id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            part_name TEXT,
            UNIQUE(model_id, part_name),
            FOREIGN KEY (model_id) REFERENCES models (id)
        )''')

        c.execute('''CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER,
            storage_size TEXT,
            color_name TEXT DEFAULT '',
            sim_type TEXT DEFAULT 'physical',
            battery_label TEXT DEFAULT '100%',
            has_box BOOLEAN DEFAULT 1,
            damage_pct TEXT DEFAULT 'Yangi',
            price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(model_id, storage_size, color_name, sim_type, battery_label, has_box, damage_pct),
            FOREIGN KEY (model_id) REFERENCES models (id)
        )''')

        imported = 0
        skipped = 0
        errors = []
        last_progress_update = 0
        batch_count = 0
        BATCH_SIZE = 100  # ✅ Har 100 qatorda commit

        def get_cell_value(row, col_name, default=''):
            """DataFrame dan to'g'ri qiymat olish"""
            try:
                if col_name in row.index:
                    val = row[col_name]
                else:
                    return str(default).strip()

                if hasattr(val, 'iloc'):
                    val = val.iloc[0] if len(val) > 0 else default
                elif hasattr(val, '__iter__') and not isinstance(val, str):
                    val_list = list(val)
                    val = val_list[0] if len(val_list) > 0 else default

                result = str(val).strip()

                if result.lower() in ['nan', 'none', 'null', '']:
                    return str(default).strip()

                return result
            except Exception as e:
                return str(default).strip()

        # ✅ 8. BATCH PROCESSING BILAN IMPORT
        for index, row in df.iterrows():
            try:
                model_name = get_cell_value(row, 'Model', '')
                storage = get_cell_value(row, 'Xotira', '')
                color = get_cell_value(row, 'Rang', '')
                sim_str = get_cell_value(row, 'SIM', '')
                battery = get_cell_value(row, 'Batareya', '100%')
                box_str = get_cell_value(row, 'Quti', '')
                damage = get_cell_value(row, 'Qismlar', 'Yangi')
                price_str = get_cell_value(row, 'Narx', '0')

                if not model_name or model_name.lower() in ['nan', 'none', 'null', '']:
                    skipped += 1
                    continue

                if not storage:
                    storage = '128GB'

                price = 0.0
                try:
                    price_clean = re.sub(r'[^\d\.]', '', price_str)
                    if price_clean:
                        price = float(price_clean)
                except:
                    price = 0.0

                sim_type = 'physical'
                if sim_str:
                    if 'esim' in sim_str.lower() or 'e-sim' in sim_str.lower():
                        sim_type = 'esim'

                has_box = 1
                if box_str:
                    if any(word in box_str.lower() for word in ['yo\'q', 'yok', 'нет', 'no', 'false', '0']):
                        has_box = 0

                damage = normalize_damage_format(damage)

                # 1. Modelni qo'shish
                c.execute("INSERT OR IGNORE INTO models (name) VALUES (?)", (model_name,))
                c.execute("SELECT id FROM models WHERE name = ?", (model_name,))
                model_result = c.fetchone()
                model_id = model_result[0] if model_result else None

                if not model_id:
                    skipped += 1
                    continue

                # 2. Xotirani qo'shish
                if storage:
                    c.execute(
                        "INSERT OR IGNORE INTO storages (model_id, size) VALUES (?, ?)",
                        (model_id, storage)
                    )

                # 3. Rangni qo'shish
                if color and color.lower() not in ['nan', 'none', '']:
                    c.execute(
                        "INSERT OR IGNORE INTO colors (model_id, name) VALUES (?, ?)",
                        (model_id, color)
                    )

                # 4. Batareyani qo'shish
                if battery:
                    c.execute(
                        "INSERT OR IGNORE INTO batteries (model_id, label) VALUES (?, ?)",
                        (model_id, battery)
                    )

                # 5. Alohida qismlarni qo'shish
                if damage and damage != "Yangi":
                    if '+' in damage:
                        parts = [p.strip() for p in damage.split('+')]
                        for part in parts:
                            c.execute(
                                "INSERT OR IGNORE INTO parts (model_id, part_name) VALUES (?, ?)",
                                (model_id, part)
                            )
                    else:
                        c.execute(
                            "INSERT OR IGNORE INTO parts (model_id, part_name) VALUES (?, ?)",
                            (model_id, damage)
                        )

                # 6. Narxni qo'shish
                try:
                    c.execute("""\
                        INSERT OR REPLACE INTO prices
                        (model_id, storage_size, color_name, sim_type, battery_label, has_box, damage_pct, price)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (model_id, storage, color or '', sim_type, battery, has_box, damage, price))

                    imported += 1
                    batch_count += 1

                    # ✅ BATCH COMMIT - har 100 qatorda
                    if batch_count >= BATCH_SIZE:
                        conn.commit()
                        conn.execute("BEGIN TRANSACTION")
                        batch_count = 0

                    # ✅ Progress yangilash - har 1000 qatorda
                    if imported - last_progress_update >= 1000 or imported == total_rows:
                        progress_text = f"⏳ {imported:,}/{total_rows:,} ta yozuv qo'shildi..."
                        try:
                            await safe_edit_message(progress_msg, progress_text)
                            last_progress_update = imported
                            await asyncio.sleep(0.05)  # ✅ CPU ga nafas
                        except:
                            pass

                except sqlite3.IntegrityError as e:
                    skipped += 1
                    if "UNIQUE constraint" not in str(e):
                        if len(errors) < 10:
                            errors.append(f"Qator {index + 2}: {str(e)[:50]}")

            except Exception as e:
                skipped += 1
                if len(errors) < 10:
                    errors.append(f"Qator {index + 2}: {str(e)[:50]}")

        # ✅ 9. FINAL COMMIT
        conn.commit()

        # ✅ 10. MEMORY CLEANUP
        try:
            del df
            os.remove(file_path)
        except:
            pass

        # 11. Natijani yuborish
        result_message = f"""\
✅ <b>IMPORT YAKUNLANDI!</b>

📊 <b>Statistika:</b>
✅ Qo'shildi: {imported:,} ta
⏭ O'tkazildi: {skipped:,} ta
📁 Fayl hajmi: {actual_size_mb:.1f} MB

🔍 <b>Bazada jami:</b>
- 📱 Modellar: {len(get_models())} ta
- 💰 Narxlar: {get_total_prices_count():,} ta
"""

        if errors:
            error_text = "\n".join(errors[:5])
            result_message += f"\n\n⚠️ <b>Xatolar ({len(errors)} ta):</b>\n<code>{error_text}</code>"

        await safe_edit_message(progress_msg, result_message)

        # 12. Namuna ko'rsatish
        if imported > 0:
            await asyncio.sleep(1)

            models = get_models()
            if models:
                sample_model = models[0]
                sample_prices = get_prices_for_model(sample_model['id'])

                if sample_prices:
                    sample_text = f"\n\n📱 <b>Namuna ({sample_model['name']}):</b>\n"
                    for i, price_row in enumerate(sample_prices[:3], 1):
                        damage_display = price_row['damage_pct'] if price_row['damage_pct'] else "Yangi"
                        sample_text += f"{i}. {price_row['storage_size']} ({damage_display}) - ${price_row['price']}\n"

                    try:
                        await safe_send_message(message, text=sample_text)
                    except:
                        pass

    except Exception as e:
        error_msg = f"❌ Importda kutilmagan xatolik:\n<code>{str(e)[:200]}</code>"
        try:
            await safe_edit_message(progress_msg, error_msg)
        except:
            try:
                await safe_send_message(message, text=error_msg)
            except:
                pass

        import traceback
        traceback.print_exc()

    finally:
        # ✅ CLEANUP
        try:
            restore_database_settings(conn)
            conn.close()
        except:
            pass

        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass

        await state.finish()

        await asyncio.sleep(2)

        try:
            await safe_send_message(
                message,
                text="🏠 Bosh menyuga qaytish uchun /start ni bosing yoki quyidagi tugmalardan foydalaning:",
                reply_markup=admin_kb()
            )
        except:
            try:
                await message.answer(
                    "🏠 Bosh menyuga qaytish uchun /start ni bosing yoki quyidagi tugmalardan foydalaning:",
                    reply_markup=admin_kb()
                )
            except:
                pass


# === EXCEL EXPORT ===
@dp.message_handler(lambda m: m.text == "📤 Excel export" and m.from_user.id in ADMINS)
async def excel_export(message: types.Message):
    try:
        progress_msg = await message.answer("⏳ Excel fayli tayyorlanmoqda...")

        conn = sqlite3.connect(DB_PATH)

        query = """\
        SELECT
            m.name as Model,
            COALESCE(s.size, '') as Xotira,
            COALESCE(c.name, '') as Rang,
            CASE
                WHEN p.sim_type = 'physical' THEN 'SIM karta'
                WHEN p.sim_type = 'esim' THEN 'eSIM'
                ELSE p.sim_type
            END as SIM,
            COALESCE(b.label, '100%') as Batareya,
            CASE WHEN p.has_box = 1 THEN 'Bor' ELSE 'Yo''q' END as Quti,
            COALESCE(p.damage_pct, 'Yangi') as Qismlar,
            p.price as Narx,
            datetime(p.created_at) as Sana
        FROM prices p
        LEFT JOIN models m ON p.model_id = m.id
        LEFT JOIN storages s ON p.model_id = s.model_id AND p.storage_size = s.size
        LEFT JOIN colors c ON p.model_id = c.model_id AND p.color_name = c.name
        LEFT JOIN batteries b ON p.model_id = b.model_id AND p.battery_label = b.label
        ORDER BY m.name, s.size, p.created_at DESC
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            await progress_msg.edit_text("❌ Bazada ma'lumot yo'q")
            return

        total_rows = len(df)
        await progress_msg.edit_text(f"✅ {total_rows} ta ma'lumot topildi\n📊 Excel fayli yaratilmoqda...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"export_{message.from_user.id}_{timestamp}.xlsx"

        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Narxlar', index=False)

            stats_df = pd.DataFrame({
                'Parametr': ['Jami yozuvlar', 'Modellar soni', 'Eksport sanasi'],
                'Qiymat': [total_rows, len(get_models()), datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
            })
            stats_df.to_excel(writer, sheet_name='Statistika', index=False)

            workbook = writer.book
            worksheet = writer.sheets['Narxlar']

            header_font = openpyxl.styles.Font(bold=True, color="FFFFFF")
            header_fill = openpyxl.styles.PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")

            for cell in worksheet[1]:
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = openpyxl.styles.Alignment(horizontal='center')

            column_widths = {
                'A': 25, 'B': 12, 'C': 15, 'D': 12,
                'E': 12, 'F': 10, 'G': 30, 'H': 15, 'I': 20,
            }

            for col, width in column_widths.items():
                worksheet.column_dimensions[col].width = width

            worksheet.auto_filter.ref = f"A1:I{total_rows + 1}"
            worksheet.freeze_panes = 'A2'

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        await progress_msg.edit_text(
            f"✅ Excel fayli tayyor: {total_rows} ta yozuv, {file_size_mb:.1f} MB\n📤 Yuborilmoqda...")

        if file_size_mb > 45:
            zip_path = f"{file_path}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.write(file_path, os.path.basename(file_path))

            await message.answer_document(
                InputFile(zip_path, filename=f"iphone_narxlari_{timestamp}.zip"),
                caption=f"📊 iPhone narxlari\n📁 {total_rows} ta yozuv\n💾 {file_size_mb:.1f} MB\n🔒 ZIP arxiv"
            )

            os.remove(zip_path)
        else:
            await message.answer_document(
                InputFile(file_path, filename=f"iphone_narxlari_{timestamp}.xlsx"),
                caption=f"📊 iPhone narxlari\n📁 {total_rows} ta yozuv\n💾 {file_size_mb:.1f} MB\n📅 {timestamp}"
            )

        os.remove(file_path)
        await progress_msg.delete()

    except Exception as e:
        error_msg = f"❌ Exportda xatolik:\n<code>{str(e)[:200]}</code>"
        try:
            await message.answer(error_msg, parse_mode="HTML")
        except:
            pass

        traceback.print_exc()


# === BAZANI TOZALASH ===
@dp.message_handler(lambda m: m.text == "🧹 Bazani tozalash" and m.from_user.id in ADMINS)
async def cleanup_database(message: types.Message):
    models_count = len(get_models())
    prices_count = get_total_prices_count()

    text = f"""\
⚠️ <b>BAZANI TOZALASH</b>

📊 <b>Joriy holat:</b>
- 📱 Modellar: {models_count} ta
- 💰 Narxlar: {prices_count} ta

<b>❌ Tozalash natijasida:</b>
1. Barcha narxlar o'chib ketadi
2. Modellar saqlanadi
3. Qismlar ma'lumotlari tozalanadi

<b>Rostan ham tozalamoqchimisiz?</b>
    """

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Ha, tozalash"), KeyboardButton("❌ Yo'q, bekor qilish"))
    kb.row(KeyboardButton("🏠 Bosh menyu"))

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await CleanupState.confirm.set()


@dp.message_handler(state=CleanupState.confirm)
async def cleanup_confirm(message: types.Message, state: FSMContext):
    if message.text == "✅ Ha, tozalash":
        try:
            success = clear_database()

            if success:
                await message.answer("✅ Baza muvaffaqiyatli tozalandi!\n📱 Modellar saqlanib qoldi.",
                                     reply_markup=admin_kb())
            else:
                await message.answer("❌ Bazani tozalashda xatolik yuz berdi",
                                     reply_markup=admin_kb())

        except Exception as e:
            await message.answer(f"❌ Xatolik: {str(e)}", reply_markup=admin_kb())

    elif message.text == "❌ Yo'q, bekor qilish":
        await message.answer("✅ Tozalash bekor qilindi", reply_markup=admin_kb())

    await state.finish()


# === NAMUNA MA'LUMOT ===
@dp.message_handler(lambda m: m.text == "📱 Namuna ma'lumot" and m.from_user.id in ADMINS)
async def sample_data(message: types.Message):
    try:
        models = get_models()
        if not models:
            await message.answer("❌ Bazada model yo'q")
            return

        model = models[0]
        model_id = model['id']

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("""\
            SELECT storage_size, color_name, battery_label, sim_type, has_box, damage_pct, price
            FROM prices
            WHERE model_id = ?
            ORDER BY price DESC
            LIMIT 5
        """, (model_id,))

        rows = c.fetchall()
        conn.close()

        if not rows:
            await message.answer(f"❌ {model['name']} uchun narxlar yo'q")
            return

        text = f"""\
<b>📱 NAMUNA MA'LUMOT</b>
Model: <b>{model['name']}</b>

<b>💰 Eng yuqori narxlar:</b>
"""

        for i, row in enumerate(rows, 1):
            storage, color, battery, sim_type, has_box, damage, price = row
            sim_display = "📲 eSIM" if sim_type == 'esim' else '📱 SIM'
            box_display = "✅ Bor" if has_box else "❌ Yo'q"
            color_display = color or "Standart"

            text += f"""\
{i}. <b>{storage}</b> | {color_display}
   {sim_display} | {box_display} | {battery}
   🔧 {damage}
   💰 <b>${float(price):,.0f}</b>
"""

        text += f"\n📊 <b>Jami:</b> {len(rows)} ta narx (faqat eng yuqori 5 tasi)"

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Xatolik: {str(e)}")




# === NOMA'LUM XABARLAR ===
@dp.message_handler()
async def unknown(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMINS

    if is_admin and message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        await message.answer("👨‍💼 Admin panel", reply_markup=admin_kb())
    else:
        await message.answer("ℹ️ Kerakli bo'limni tanlang:", reply_markup=main_menu(is_admin))