"""
STATISTIKA HANDLERS - Aiogram 2.25.2
"""
import traceback
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

from loader import dp, bot
from data.config import ADMINS
from utils.db_api.stats_database import (
    add_or_update_user, get_user_stats, get_global_stats,
    get_recent_history, get_daily_stats, get_model_stats,
    save_price_inquiry, get_conn
)


class StatsState(StatesGroup):
    """Statistika holatlari"""
    viewing_stats = State()
    viewing_history = State()
    viewing_model_stats = State()


def stats_main_menu():
    """Statistika asosiy menu"""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📊 Mening statistikam", callback_data="stats:my"),
        InlineKeyboardButton("🌍 Umumiy statistika", callback_data="stats:global"),
        InlineKeyboardButton("📱 Model statistikasi", callback_data="stats:models"),
        InlineKeyboardButton("📜 Mening tarixim", callback_data="stats:history"),
        InlineKeyboardButton("📈 Kunlik statistika", callback_data="stats:daily"),
        InlineKeyboardButton("◀️ Orqaga", callback_data="stats:back")
    )
    return kb


def stats_period_menu(stat_type="my"):
    """Davr tanlash menu"""
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📅 Bugun", callback_data=f"stats:{stat_type}:today"),
        InlineKeyboardButton("📆 Hafta", callback_data=f"stats:{stat_type}:week"),
        InlineKeyboardButton("📊 Oy", callback_data=f"stats:{stat_type}:month"),
        InlineKeyboardButton("📈 Hammasi", callback_data=f"stats:{stat_type}:all")
    )
    kb.add(InlineKeyboardButton("◀️ Orqaga", callback_data="stats:menu"))
    return kb


def back_to_stats_kb():
    """Statistikaga qaytish"""
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Statistikaga", callback_data="stats:menu"))
    return kb


# ==================== KOMANDALAR ====================

@dp.message_handler(commands=['stats', 'statistika'])
async def stats_command(message: types.Message):
    """Statistika komandasi"""
    user = message.from_user

    # Foydalanuvchini saqlash
    add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    text = "📊 <b>STATISTIKA</b>\n\n"
    text += "Quyidagi bo'limlardan birini tanlang:"

    await message.answer(
        text,
        reply_markup=stats_main_menu(),
        parse_mode='HTML'
    )


# ==================== CALLBACK HANDLERS ====================

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('stats:'))
async def stats_callback_handler(callback: types.CallbackQuery, state: FSMContext):
    """Statistika callback handler"""
    await callback.answer()

    user = callback.from_user
    data = callback.data

    # Foydalanuvchini yangilash
    add_or_update_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name
    )

    try:
        if data == "stats:menu":
            await show_stats_menu(callback)

        elif data == "stats:my":
            await show_my_stats_menu(callback)

        elif data.startswith("stats:my:"):
            period = data.split(":")[-1]
            await show_my_stats_detail(callback, period)

        elif data == "stats:global":
            await show_global_stats_menu(callback)

        elif data.startswith("stats:global:"):
            period = data.split(":")[-1]
            await show_global_stats_detail(callback, period)

        elif data == "stats:history":
            await show_history(callback)

        elif data == "stats:daily":
            await show_daily_stats(callback)

        elif data == "stats:models":
            await show_models_menu(callback)

        elif data.startswith("stats:model:"):
            model_name = data.replace("stats:model:", "")
            await show_model_detail(callback, model_name)

        elif data == "stats:back":
            await callback.message.delete()

    except Exception as e:
        print(f"❌ Statistika xato: {e}")
        print(traceback.format_exc())
        await callback.message.answer("❌ Xatolik yuz berdi")


async def show_stats_menu(callback: types.CallbackQuery):
    """Statistika asosiy menu"""
    text = "📊 <b>STATISTIKA</b>\n\n"
    text += "Quyidagi bo'limlardan birini tanlang:"

    await callback.message.edit_text(
        text,
        reply_markup=stats_main_menu(),
        parse_mode='HTML'
    )


async def show_my_stats_menu(callback: types.CallbackQuery):
    """Shaxsiy statistika menu"""
    text = "📊 <b>MENING STATISTIKAM</b>\n\n"
    text += "Davrni tanlang:"

    await callback.message.edit_text(
        text,
        reply_markup=stats_period_menu("my"),
        parse_mode='HTML'
    )


async def show_my_stats_detail(callback: types.CallbackQuery, period: str):
    """Shaxsiy statistika detali"""
    user_id = callback.from_user.id
    stats = get_user_stats(user_id, period)

    period_names = {
        'today': 'BUGUN',
        'week': 'SHU HAFTA',
        'month': 'SHU OY',
        'all': 'BARCHA VAQT'
    }

    text = f"📊 <b>STATISTIKA - {period_names[period]}</b>\n\n"

    if not stats or stats['total_inquiries'] == 0:
        text += "❌ Hali ma'lumot yo'q"
    else:
        text += f"🔢 Jami narxlatishlar: <b>{stats['total_inquiries']}</b>\n"
        text += f"📱 Turli modellar: <b>{stats['unique_models']}</b>\n"
        text += f"📅 Faol kunlar: <b>{stats['active_days']}</b>\n"

        if stats.get('top_models'):
            text += f"\n<b>🏆 TOP modellar:</b>\n"
            for i, model in enumerate(stats['top_models'], 1):
                text += f"{i}. {model['model_name']} - {model['count']} marta\n"

    await callback.message.edit_text(
        text,
        reply_markup=stats_period_menu("my"),
        parse_mode='HTML'
    )


async def show_global_stats_menu(callback: types.CallbackQuery):
    """Umumiy statistika menu"""
    text = "🌍 <b>UMUMIY STATISTIKA</b>\n\n"
    text += "Davrni tanlang:"

    await callback.message.edit_text(
        text,
        reply_markup=stats_period_menu("global"),
        parse_mode='HTML'
    )


async def show_global_stats_detail(callback: types.CallbackQuery, period: str):
    """Umumiy statistika detali"""
    stats = get_global_stats(period)

    period_names = {
        'today': 'BUGUN',
        'week': 'SHU HAFTA',
        'month': 'SHU OY',
        'all': 'BARCHA VAQT'
    }

    text = f"🌍 <b>UMUMIY STATISTIKA - {period_names[period]}</b>\n\n"
    text += f"🔢 Jami narxlatishlar: <b>{stats['total_inquiries']}</b>\n"
    text += f"👥 Faol foydalanuvchilar: <b>{stats['active_users']}</b>\n"
    text += f"📱 Turli modellar: <b>{stats['unique_models']}</b>\n"

    if stats.get('top_models'):
        text += f"\n<b>🏆 TOP modellar:</b>\n"
        for i, model in enumerate(stats['top_models'][:5], 1):
            text += f"{i}. {model['model_name']} - {model['count']} marta\n"

    if stats.get('top_users'):
        text += f"\n<b>👑 TOP foydalanuvchilar:</b>\n"
        for i, user in enumerate(stats['top_users'][:5], 1):
            name = user.get('first_name') or user.get('username') or "Anonim"
            text += f"{i}. {name} - {user['count']} marta\n"

    await callback.message.edit_text(
        text,
        reply_markup=stats_period_menu("global"),
        parse_mode='HTML'
    )


async def show_history(callback: types.CallbackQuery):
    """Narxlatish tarixi"""
    user_id = callback.from_user.id
    history = get_recent_history(user_id, limit=10)

    text = "📜 <b>MENING TARIXIM</b>\n"
    text += "<i>Oxirgi 10 ta narxlatish</i>\n\n"

    if not history:
        text += "❌ Hali ma'lumot yo'q"
    else:
        for i, item in enumerate(history, 1):
            date_str = item['created_at'][:16].replace('T', ' ')
            box_emoji = "📦" if item['has_box'] == 1 else "❌"

            text += f"<b>{i}. {item['model_name']}</b>\n"
            text += f"   💾 {item['storage_size']} | 🎨 {item['color_name']}\n"
            text += f"   📡 {item['sim_type']} | 🔋 {item['battery_label']}\n"
            text += f"   {box_emoji} Box | 💥 {item['damage_pct']}\n"
            text += f"   💰 <b>{item['final_price']}</b>\n"
            text += f"   🕐 {date_str}\n\n"

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔄 Yangilash", callback_data="stats:history"),
        InlineKeyboardButton("◀️ Orqaga", callback_data="stats:menu")
    )

    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode='HTML'
    )


async def show_daily_stats(callback: types.CallbackQuery):
    """Kunlik statistika"""
    stats = get_daily_stats(days=7)

    text = "📊 <b>KUNLIK STATISTIKA</b>\n"
    text += "<i>Oxirgi 7 kun</i>\n\n"

    if not stats:
        text += "❌ Ma'lumot yo'q"
    else:
        for item in stats:
            bars = "▓" * min((item['count'] // 5), 20) if item['count'] > 0 else "▓"
            text += f"<b>{item['date']}</b>\n"
            text += f"  📊 {bars} {item['count']} ta\n"
            text += f"  👥 {item['users']} foydalanuvchi\n\n"

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("🔄 Yangilash", callback_data="stats:daily"),
        InlineKeyboardButton("◀️ Orqaga", callback_data="stats:menu")
    )

    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode='HTML'
    )


async def show_models_menu(callback: types.CallbackQuery):
    """Modellar menu"""
    from utils.db_api.database import get_models

    models = get_models()

    text = "📱 <b>MODEL STATISTIKASI</b>\n\n"
    text += "Modelni tanlang:"

    kb = InlineKeyboardMarkup(row_width=1)

    for model in models[:20]:
        kb.add(InlineKeyboardButton(
            model['name'],
            callback_data=f"stats:model:{model['name']}"
        ))

    kb.add(InlineKeyboardButton("◀️ Orqaga", callback_data="stats:menu"))

    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode='HTML'
    )


async def show_model_detail(callback: types.CallbackQuery, model_name: str):
    """Model detali"""
    stats = get_model_stats(model_name, period='all')

    text = f"📱 <b>{model_name} - STATISTIKA</b>\n\n"
    text += f"🔢 Jami so'rovlar: <b>{stats['total_inquiries']}</b>\n"
    text += f"👥 Foydalanuvchilar: <b>{stats['unique_users']}</b>\n"

    if stats.get('top_configs'):
        text += f"\n<b>🔥 TOP konfiguratsiyalar:</b>\n"
        for i, config in enumerate(stats['top_configs'], 1):
            text += f"{i}. {config['storage_size']} - {config['color_name']}: {config['count']} marta\n"

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("◀️ Orqaga", callback_data="stats:models"))

    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode='HTML'
    )


# ==================== HELPER FUNKSIYALAR ====================

def format_price(price):
    """Narxni formatlash"""
    try:
        if isinstance(price, (int, float)):
            return f"{int(price):,}".replace(',', ' ') + " $"
        else:
            price_clean = str(price).replace('$', '').replace(',', '').replace(' ', '').strip()
            price_float = float(price_clean)
            return f"{int(price_float):,}".replace(',', ' ') + " $"
    except:
        return str(price)