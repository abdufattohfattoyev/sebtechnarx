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
from utils.db_api.stats_database import add_or_update_user, save_price_inquiry
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
MAX_FILE_SIZE_MB = 20


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
        KeyboardButton("📱 iPhone narxini bilish"),
        KeyboardButton("ℹ️ Biz haqimizda")
    )

    # Ikkinchi qator
    if is_admin:
        kb.row(
            KeyboardButton("🔧 Admin panel"),
            KeyboardButton("👨‍💼 Admin bilan aloqa")
        )
    else:
        kb.row(
            KeyboardButton("👨‍💼 Admin bilan aloqa")
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

# === START ===
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user = message.from_user

    # Foydalanuvchi telefon raqamini yuborganligini tekshirish
    user_data = add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    # Agar telefon raqami yo'q bo'lsa, so'rash
    if not user_data or not user_data.get('phone_number'):
        text = f"""\
👋 Assalomu alaykum, <b>{user.full_name}</b>!

📱 iPhone narxlarini aniq hisoblaymiz

<b>⬇️ Davom etish uchun telefon raqamingizni yuboring:</b>
"""
        await message.answer(text, reply_markup=phone_request_kb(), parse_mode="HTML")
        await UserState.waiting_phone.set()
    else:
        # Telefon raqami mavjud bo'lsa, asosiy menyuni ko'rsatish
        models = get_models()
        text = f"""\
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

    # Telefon raqamni bazaga saqlash
    add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=phone
    )

    models = get_models()
    text = f"""\
✅ Rahmat, <b>{user.full_name}</b>!

📱 iPhone narxlarini aniq hisoblaymiz
✅ Hozir <b>{len(models)}</b> ta model mavjud

<b>⬇️ Quyidagi menyulardan birini tanlang:</b>
"""
    await message.answer(text, reply_markup=main_menu(user.id in ADMINS), parse_mode="HTML")
    await state.finish()


# === MODEL TANLASH ===
@dp.message_handler(lambda m: m.text == "📱 iPhone narxini bilish")
async def choose_model(message: types.Message, state: FSMContext):
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
        data = await state.get_data()
        msg = types.Message(text=data.get('model_name', ''))
        msg.from_user = message.from_user
        await model_selected(msg, state)
    elif current == UserState.waiting_battery.state:
        data = await state.get_data()
        msg = types.Message(text=data.get('storage', ''))
        msg.from_user = message.from_user
        await storage_selected(msg, state)
    elif current in [UserState.waiting_sim.state, UserState.waiting_box.state]:
        data = await state.get_data()
        msg = types.Message(text=data.get('color', 'Standart'))
        msg.from_user = message.from_user
        await color_selected(msg, state)
    elif current == UserState.waiting_parts_choice.state:
        data = await state.get_data()
        msg = types.Message(text=data.get('has_box', 'Bor'))
        msg.from_user = message.from_user
        await box_selected(msg, state)
    elif current == UserState.waiting_parts.state:
        data = await state.get_data()
        await state.update_data(selected_parts=[])
        # Inline callback orqali qaytish
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

    # Rang nomlarini olish
    color_names = [c['name'] for c in colors]

    # Klaviatura yaratish (qatorda 2 ta tugma)
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
async def show_final_price(message: types.Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get('selected_parts', [])
    color = data.get('color') or ""

    if not selected:
        damage_pct = "Yangi"
        damage_display = "Yangi"
    else:
        damage_pct = "+".join(sorted(selected))
        damage_display = data.get('damage_display', " + ".join([PARTS[k] for k in sorted(selected)]))

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

    # Xabar
    text = f"""\
📊 <b>HISOBLASH NATIJASI:</b>

📱 <b>Model:</b> {data['model_name']}
💾 <b>Xotira:</b> {data['storage']}
🎨 <b>Rang:</b> {color or 'Standart'}
📞 <b>SIM:</b> {'📲 eSIM' if data['sim_type'] == 'esim' else '📱 SIM karta'}
🔋 <b>Batareya:</b> {data['battery']}
📦 <b>Quti:</b> {'✅ Bor' if data['has_box'] == 'Bor' else '❌ Yoq'}
🔧 <b>Holat:</b> {damage_display}

💰 <b>TAXMINIY NARX:</b> {price_text}

<i>Narxlar taxminiy, bozordagi narxlar farq qilishi mumkin.</i>
    """.strip()

    # Yakuniy klaviatura (2 qatordan)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(
        KeyboardButton("🔄 Yana hisoblash"),
        KeyboardButton("🏠 Bosh menyu")
    )

    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.finish()


# === YANA HISOBLASH ===
@dp.message_handler(lambda m: m.text == "🔄 Yana hisoblash")
async def again(message: types.Message, state: FSMContext):
    await choose_model(message, state)


# === ADMIN BILAN ALOQA ===
@dp.message_handler(lambda m: m.text == "👨‍💼 Admin bilan aloqa")
async def contact_admin(message: types.Message):
    text = """\
<b>👨‍💼 ADMIN BILAN ALOQA</b>

📞 <b>Murojaat uchun:</b>
- Telegram: @FATTOYEVABDUFATTOH
- Telefon: +998 93 799 70 04

📝 <b>Savollar:</b>
- Narxlar haqida
- Bot ishida xatoliklar
- Yangi imkoniyatlar

💬 <b>Ishlash vaqti:</b>
Har kuni 09:00 - 21:00

<i>Tez orada javob beramiz!</i>
"""
    await message.answer(text, parse_mode="HTML")


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
        # 1. Faylni yuklash
        await message.document.download(destination_file=file_path)

        # 2. Fayl hajmini tekshirish
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            await safe_edit_message(
                progress_msg,
                f"❌ Fayl juda katta: {file_size_mb:.1f} MB (maks: {MAX_FILE_SIZE_MB} MB)"
            )
            os.remove(file_path)
            await state.finish()
            return

        await safe_edit_message(
            progress_msg,
            f"✅ Fayl yuklandi: {file_size_mb:.1f} MB\n📊 Ma'lumotlar tahlil qilinmoqda..."
        )

        # 3. Excelni o'qish
        try:
            df = pd.read_excel(file_path, dtype=str)
        except Exception as e:
            try:
                df = pd.read_excel(file_path, engine='xlrd', dtype=str)
            except Exception as e2:
                await safe_edit_message(
                    progress_msg,
                    f"❌ Excel faylni ochib bo'lmadi:\n{e}\n\nYoki:\n{e2}"
                )
                os.remove(file_path)
                await state.finish()
                return

        # 4. Ma'lumotlarni tozalash
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

        # 5. Kerakli ustunlarni tekshirish
        required_columns = ['Model', 'Narx']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            await safe_edit_message(
                progress_msg,
                f"❌ Quyidagi ustunlar topilmadi: {', '.join(missing_columns)}"
            )
            os.remove(file_path)
            await state.finish()
            return

        total_rows = len(df)
        await safe_edit_message(
            progress_msg,
            f"✅ {total_rows} ta ma'lumot topildi\n🔄 Bazaga yozilmoqda... (0/{total_rows})"
        )

        # 6. Optimallashtirilgan bazaga ulanish
        conn = optimize_database_for_import()
        c = conn.cursor()

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
                print(f"get_cell_value xato: {col_name}, {e}")
                return str(default).strip()

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
                    errors.append(f"Qator {index + 2}: Model '{model_name}' saqlanmadi")
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

                    # Progress yangilash
                    if imported - last_progress_update >= 250 or imported == total_rows:
                        progress_text = f"⏳ {imported}/{total_rows} ta yozuv qo'shildi..."
                        try:
                            await safe_edit_message(progress_msg, progress_text)
                            last_progress_update = imported
                            await asyncio.sleep(0.1)
                        except:
                            pass

                except sqlite3.IntegrityError as e:
                    skipped += 1
                    if "UNIQUE constraint" not in str(e):
                        errors.append(f"Qator {index + 2}: {str(e)[:50]}")

            except Exception as e:
                skipped += 1
                if len(errors) < 10:
                    errors.append(f"Qator {index + 2}: {str(e)[:50]}")

        # 7. Commit qilish
        conn.commit()

        # 8. Natijani yuborish
        result_message = f"""\
✅ <b>IMPORT YAKUNLANDI!</b>

📊 <b>Statistika:</b>
✅ Qo'shildi: {imported} ta
⏭ O'tkazildi: {skipped} ta
📁 Fayl hajmi: {file_size_mb:.1f} MB

🔍 <b>Bazada jami:</b>
- 📱 Modellar: {len(get_models())} ta
- 💰 Narxlar: {get_total_prices_count()} ta
        """

        if errors:
            error_text = "\n".join(errors[:5])
            result_message += f"\n\n⚠️ <b>Xatolar ({len(errors)} ta):</b>\n<code>{error_text}</code>"

        await safe_edit_message(progress_msg, result_message)

        # 9. Namuna ko'rsatish
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

        traceback.print_exc()

    finally:
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


# === STATISTIKA ===
@dp.message_handler(lambda m: m.text == "📊 Statistika" and m.from_user.id in ADMINS)
async def admin_statistics(message: types.Message):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM models")
        models_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM prices")
        prices_count = c.fetchone()[0]

        c.execute("SELECT COUNT(DISTINCT model_id) FROM prices")
        active_models = c.fetchone()[0]

        c.execute("""\
            SELECT m.name, COUNT(p.id) as count
            FROM prices p
            JOIN models m ON p.model_id = m.id
            GROUP BY p.model_id
            ORDER BY count DESC
            LIMIT 5
        """)
        top_models = c.fetchall()

        c.execute("SELECT MIN(price), MAX(price), AVG(price) FROM prices WHERE price > 0")
        min_price, max_price, avg_price = c.fetchone()

        c.execute("SELECT MAX(created_at) FROM prices")
        last_update = c.fetchone()[0]

        conn.close()

        text = f"""\
<b>📊 ADMIN STATISTIKA</b>

<b>📈 Umumiy ko'rsatkichlar:</b>
- 📱 Modellar: {models_count} ta
- 💰 Narxlar: {prices_count} ta
- ✅ Faol modellar: {active_models} ta

<b>💰 Narxlar diapazoni:</b>
- 📉 Minimal: ${min_price or 0:,.0f}
- 📈 Maksimal: ${max_price or 0:,.0f}
- 📊 O'rtacha: ${avg_price or 0:,.0f}

<b>🏆 Top modellar (narxlar soni):</b>
"""

        for i, (model, count) in enumerate(top_models, 1):
            text += f"{i}. {model}: {count} ta\n"

        text += f"\n<b>📅 Oxirgi yangilanish:</b> {last_update or 'Nomalum'}"
        text += f"\n<b>🕐 Joriy vaqt:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        await message.answer(text, parse_mode="HTML")

    except Exception as e:
        await message.answer(f"❌ Statistika olishda xato: {str(e)}")


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


# === BIZ HAQIMIZDA ===
@dp.message_handler(lambda m: m.text == "ℹ️ Biz haqimizda")
async def about(message: types.Message):
    text = """\
<b>📱 iPhone Narx Hisoblagich</b>

🤖 <b>Bot haqida:</b>
- iPhone modellari narxlarini hisoblaydi
- Real bozor narxlari asosida
- 100+ turdagi konfiguratsiyalar

🔧 <b>Imkoniyatlar:</b>
- Barcha iPhone modellari
- Xotira, rang, batareya tanlash
- SIM turi va quti holati
- Almashgan qismlarni hisobga olish

👨‍💻 <b>Dasturchi:</b> @FATTOYEVABDUFATTOH

📞 <b>Aloqa:</b>
- Taklif va shikoyatlar uchun: @FATTOYEVABDUFATTOH
- Yangiliklar: @iphone_uzb

<i>Bot doimiy yangilanib boriladi!</i>
"""

    await message.answer(text, parse_mode="HTML")


# === NOMA'LUM XABARLAR ===
@dp.message_handler()
async def unknown(message: types.Message):
    user_id = message.from_user.id
    is_admin = user_id in ADMINS

    if is_admin and message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        await message.answer("👨‍💼 Admin panel", reply_markup=admin_kb())
    else:
        await message.answer("ℹ️ Kerakli bo'limni tanlang:", reply_markup=main_menu(is_admin))