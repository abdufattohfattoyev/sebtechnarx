# handlers/admin.py - TO'LIQ VERSIYA (AIOGRAM 2.25.2)
import os
import re
import asyncio
import traceback
from datetime import datetime
import pandas as pd
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.exceptions import RetryAfter

from loader import dp, bot
from keyboards.default.knopkalar import admin_kb, cleanup_confirm_kb
from data.config import ADMINS

# ============================================
# POSTGRESQL IMPORT - PHONE DATABASE
# ============================================
from utils.db_api.database import (
    get_models, get_model, add_model,
    get_storages, add_storage,
    get_colors, add_color,
    get_batteries, add_battery,
    get_sim_types, add_sim_type,
    add_part,
    add_price_record,
    clear_all_prices,
    get_total_prices_count,
    normalize_damage_format,
    get_conn
)

# ============================================
# USER DATABASE IMPORT
# ============================================
from utils.db_api.user_database import (
    get_users_statistics,
    get_detailed_users_statistics,
    get_all_users_count,
    get_total_pricings
)

# ============================================
# KONSTANTALAR (OPTIMIZED)
# ============================================
MAX_FILE_SIZE_MB = 50
BATCH_SIZE = 10000  # Katta batch = kamroq database query
PROGRESS_UPDATE_INTERVAL = 2000  # Kamroq yangilanish = tezroq ishlash


# ============================================
# STATE'LAR
# ============================================
class ImportState(StatesGroup):
    waiting_file = State()


class CleanupState(StatesGroup):
    confirm = State()


# ============================================
# YORDAMCHI FUNKSIYALAR
# ============================================

async def safe_edit_message(progress_msg, text, parse_mode="HTML"):
    """Xabarni xavfsiz tahrirlash"""
    try:
        await progress_msg.edit_text(text, parse_mode=parse_mode)
    except RetryAfter as e:
        await asyncio.sleep(e.timeout)
        await progress_msg.edit_text(text, parse_mode=parse_mode)
    except Exception:
        pass


def get_cell_value(row, col_name, default=''):
    """Excel katak qiymatini olish"""
    try:
        val = row[col_name]
        if pd.isna(val):
            return str(default)
        return str(val).strip()
    except:
        return str(default)


def detect_columns(df_columns):
    """Ustunlarni avtomatik aniqlash"""
    mapping = {
        'model': None,
        'storage': None,
        'color': None,
        'sim': None,
        'battery': None,
        'box': None,
        'damage': None,
        'price': None
    }

    # Model
    for col in df_columns:
        col_lower = col.lower()
        if 'model' in col_lower or 'телефон' in col_lower:
            mapping['model'] = col
            break

    # Storage
    for col in df_columns:
        col_lower = col.lower()
        if 'xotira' in col_lower or 'storage' in col_lower or 'память' in col_lower or 'gb' in col_lower:
            mapping['storage'] = col
            break

    # Color
    for col in df_columns:
        col_lower = col.lower()
        if 'rang' in col_lower or 'color' in col_lower or 'цвет' in col_lower:
            mapping['color'] = col
            break

    # SIM
    for col in df_columns:
        col_lower = col.lower()
        if 'sim' in col_lower:
            mapping['sim'] = col
            break

    # Battery
    for col in df_columns:
        col_lower = col.lower()
        if 'batar' in col_lower or 'battery' in col_lower or 'батарея' in col_lower or 'akkum' in col_lower:
            mapping['battery'] = col
            break

    # Box
    for col in df_columns:
        col_lower = col.lower()
        if 'quti' in col_lower or 'box' in col_lower or 'коробка' in col_lower:
            mapping['box'] = col
            break

    # Damage
    for col in df_columns:
        col_lower = col.lower()
        if 'qism' in col_lower or 'damage' in col_lower or 'повреж' in col_lower or 'част' in col_lower:
            mapping['damage'] = col
            break

    # Price
    for col in df_columns:
        col_lower = col.lower()
        if 'narx' in col_lower or 'price' in col_lower or 'цена' in col_lower or 'сум' in col_lower or 'usd' in col_lower:
            mapping['price'] = col
            break

    return mapping


# ============================================
# BULK INSERT FUNKSIYASI (TEZKOR)
# ============================================

def bulk_insert_prices(prices_batch):
    """
    Bir nechta narxlarni bir vaqtning o'zida qo'shish
    PostgreSQL COPY yoki VALUES bilan - 10x tezroq!
    """
    if not prices_batch:
        return 0

    try:
        conn = get_conn()
        cursor = conn.cursor()

        # VALUES qismini tayyorlash
        values_list = []
        for item in prices_batch:
            values_list.append(
                f"({item['model_id']}, "
                f"'{item['storage_size']}', "
                f"'{item['color_name']}', "
                f"'{item['sim_type']}', "
                f"'{item['battery_label']}', "
                f"{item['has_box']}, "
                f"'{item['damage_pct']}', "
                f"{item['price']}, "
                f"CURRENT_TIMESTAMP, "
                f"CURRENT_TIMESTAMP)"
            )

        values_str = ','.join(values_list)

        # Bir SQL bilan hammасini qo'shish
        query = f"""
            INSERT INTO prices 
            (model_id, storage_size, color_name, sim_type, battery_label, 
             has_box, damage_pct, price, created_at, updated_at)
            VALUES {values_str}
            ON CONFLICT (model_id, storage_size, color_name, sim_type, battery_label, has_box, damage_pct)
            DO UPDATE SET 
                price = EXCLUDED.price,
                updated_at = EXCLUDED.updated_at
        """

        cursor.execute(query)
        conn.commit()

        inserted = cursor.rowcount
        cursor.close()
        conn.close()

        return inserted

    except Exception as e:
        print(f"Bulk insert error: {e}")
        return 0


# ============================================
# IMPORT BOSHLASH
# ============================================

@dp.message_handler(lambda msg: msg.text == "📥 Narxlarni import qilish", user_id=ADMINS)
async def import_prices_start(message: types.Message):
    """Import jarayonini boshlash"""
    await message.answer(
        "📄 <b>Excel faylni yuboring</b>\n\n"
        "📋 Fayl formati:\n"
        "• Model, Xotira, Rang, SIM, Batareya, Quti, Qismlar, Narx\n\n"
        "⚠️ Maksimal hajm: 50MB\n"
        "🚀 Tezkor yuklash rejimi yoqilgan!",
        parse_mode="HTML"
    )
    await ImportState.waiting_file.set()


# ============================================
# IMPORT JARAYONI (SUPER OPTIMIZED)
# ============================================

@dp.message_handler(content_types=['document'], state=ImportState.waiting_file)
async def process_import(message: types.Message, state: FSMContext):
    """Excel faylni import qilish - SUPER TEZKOR"""

    user_id = message.from_user.id
    if user_id not in ADMINS:
        return

    # ============================================
    # 1. FAYLNI TEKSHIRISH
    # ============================================
    file_name = message.document.file_name
    file_size_mb = message.document.file_size / (1024 * 1024)

    if not file_name.lower().endswith(('.xlsx', '.xls')):
        await message.answer("❌ Faqat Excel fayllar (.xlsx, .xls)!")
        return

    if file_size_mb > MAX_FILE_SIZE_MB:
        await message.answer(f"❌ Fayl juda katta! Maksimal: {MAX_FILE_SIZE_MB}MB")
        return

    progress_msg = await message.answer(
        f"⚡ <b>Tezkor yuklash...</b>\n"
        f"📦 Hajm: {file_size_mb:.2f}MB",
        parse_mode="HTML"
    )

    file_path = f"temp_{user_id}_{datetime.now().timestamp()}.xlsx"
    start_time = datetime.now()

    try:
        # ============================================
        # 2. FAYLNI YUKLAB OLISH
        # ============================================
        try:
            await asyncio.wait_for(
                message.document.download(destination_file=file_path),
                timeout=300.0
            )
        except asyncio.TimeoutError:
            await message.answer("❌ Fayl yuklanish vaqti tugadi (5 min). Kichikroq fayl yuboring!")
            return
        except Exception as e:
            await message.answer(f"❌ Fayl yuklanishda xato: {e}")
            return

        await safe_edit_message(progress_msg, "📊 O'qilmoqda...")

        # ============================================
        # 3. EXCEL NI O'QISH
        # ============================================
        try:
            df = pd.read_excel(file_path, dtype=str, engine='openpyxl')
            df.columns = [str(c).strip() for c in df.columns]
        except Exception as e:
            await message.answer(f"❌ Excel o'qishda xato: {e}")
            return

        total_rows = len(df)

        if total_rows == 0:
            await message.answer("❌ Fayl bo'sh!")
            return

        # ============================================
        # 4. USTUNLARNI ANIQLASH
        # ============================================
        col_map = detect_columns(df.columns)

        if not col_map['model'] or not col_map['price']:
            await message.answer(
                "❌ <b>Zarur ustunlar topilmadi!</b>\n\n"
                "Kerakli ustunlar:\n"
                "• Model (majburiy)\n"
                "• Narx (majburiy)",
                parse_mode="HTML"
            )
            return

        await safe_edit_message(
            progress_msg,
            f"🔄 <b>Tayyorlanmoqda...</b>\n"
            f"📊 Qatorlar: {total_rows:,}",
            parse_mode="HTML"
        )

        # ============================================
        # 5. MA'LUMOTLARNI TAYYORLASH
        # ============================================
        models_to_add = set()
        prices_data = []
        skipped = 0

        for index, row in df.iterrows():
            model_name = get_cell_value(row, col_map['model'])
            if not model_name:
                skipped += 1
                continue

            price_raw = get_cell_value(row, col_map['price'], '0')
            price_clean = re.sub(r'[^\d.]', '', price_raw)
            price = float(price_clean) if price_clean else 0

            if price <= 0:
                skipped += 1
                continue

            models_to_add.add(model_name)

            storage = get_cell_value(row, col_map['storage'], '128GB') if col_map['storage'] else '128GB'
            color = get_cell_value(row, col_map['color'], '') if col_map['color'] else ''

            sim_raw = get_cell_value(row, col_map['sim'], 'physical') if col_map['sim'] else 'physical'
            sim_type = 'esim' if 'esim' in sim_raw.lower() else 'physical'

            battery = get_cell_value(row, col_map['battery'], '100%') if col_map['battery'] else '100%'

            box_raw = get_cell_value(row, col_map['box'], 'Bor') if col_map['box'] else 'Bor'
            has_box = any(x in box_raw.lower() for x in ['bor', 'ha', 'yes', '1'])

            damage_raw = get_cell_value(row, col_map['damage'], 'Yangi') if col_map['damage'] else 'Yangi'
            damage = normalize_damage_format(damage_raw)

            prices_data.append({
                'model': model_name,
                'storage': storage,
                'color': color,
                'sim': sim_type,
                'battery': battery,
                'box': has_box,
                'damage': damage,
                'price': price
            })

        valid_count = len(prices_data)

        if valid_count == 0:
            await message.answer("❌ Yaroqli ma'lumotlar topilmadi!")
            return

        # ============================================
        # 6. MODELLAR VA PARAMETRLARNI QO'SHISH
        # ============================================
        await safe_edit_message(
            progress_msg,
            f"📱 <b>Modellar qo'shilmoqda...</b>\n"
            f"📊 {len(models_to_add)} ta model",
            parse_mode="HTML"
        )

        model_ids = {}
        unique_storages = {}
        unique_colors = {}
        unique_batteries = {}
        unique_sim_types = {}

        try:
            conn = get_conn()
            cursor = conn.cursor()

            # Modellarni qo'shish
            for model_name in models_to_add:
                cursor.execute(
                    "INSERT INTO models (name) VALUES (%s) ON CONFLICT (name) DO NOTHING RETURNING id",
                    (model_name,)
                )
                result = cursor.fetchone()
                if result:
                    model_ids[model_name] = result[0]
                else:
                    cursor.execute("SELECT id FROM models WHERE name = %s", (model_name,))
                    model_ids[model_name] = cursor.fetchone()[0]

            conn.commit()

            # Parametrlarni yig'ish
            for item in prices_data:
                model_name = item['model']
                model_id = model_ids.get(model_name)

                if not model_id:
                    continue

                if model_id not in unique_storages:
                    unique_storages[model_id] = set()
                unique_storages[model_id].add(item['storage'])

                if model_id not in unique_colors:
                    unique_colors[model_id] = set()
                if item['color']:
                    unique_colors[model_id].add(item['color'])

                if model_id not in unique_batteries:
                    unique_batteries[model_id] = set()
                unique_batteries[model_id].add(item['battery'])

                if model_id not in unique_sim_types:
                    unique_sim_types[model_id] = set()
                unique_sim_types[model_id].add(item['sim'])

            # Parametrlarni qo'shish
            for model_id, storages in unique_storages.items():
                for storage in storages:
                    cursor.execute(
                        "INSERT INTO storages (model_id, size) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (model_id, storage)
                    )

            for model_id, colors in unique_colors.items():
                for color in colors:
                    cursor.execute(
                        "INSERT INTO colors (model_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (model_id, color)
                    )

            for model_id, batteries in unique_batteries.items():
                for battery in batteries:
                    cursor.execute(
                        "INSERT INTO batteries (model_id, label) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (model_id, battery)
                    )

            for model_id, sim_types in unique_sim_types.items():
                for sim_type in sim_types:
                    cursor.execute(
                        "INSERT INTO sim_types (model_id, type) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                        (model_id, sim_type)
                    )

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            print(f"Models/params error: {e}")
            conn.rollback()

        # ============================================
        # 7. NARXLARNI BULK INSERT
        # ============================================
        await safe_edit_message(
            progress_msg,
            f"💾 <b>Narxlar yuklanmoqda...</b>\n"
            f"⚡ Tezkor rejim\n"
            f"📊 {valid_count:,} ta",
            parse_mode="HTML"
        )

        success_count = 0
        error_count = 0
        last_update_time = datetime.now()
        bulk_batch = []

        for i, item in enumerate(prices_data):
            model_id = model_ids.get(item['model'])
            if not model_id:
                error_count += 1
                continue

            damage_normalized = item['damage']
            if not damage_normalized or damage_normalized.lower() in ['yangi', 'nan', 'none']:
                damage_normalized = "Yangi"
            else:
                damage_normalized = normalize_damage_format(damage_normalized)

            bulk_batch.append({
                'model_id': model_id,
                'storage_size': item['storage'].replace("'", "''"),
                'color_name': item['color'].replace("'", "''"),
                'sim_type': item['sim'],
                'battery_label': item['battery'].replace("'", "''"),
                'has_box': 'TRUE' if item['box'] else 'FALSE',
                'damage_pct': damage_normalized.replace("'", "''"),
                'price': item['price']
            })

            if len(bulk_batch) >= BATCH_SIZE or i == len(prices_data) - 1:
                # Dublikatlarni tozalash
                unique_batch = []
                seen_keys = set()

                for batch_item in bulk_batch:
                    key = (
                        batch_item['model_id'],
                        batch_item['storage_size'],
                        batch_item['color_name'],
                        batch_item['sim_type'],
                        batch_item['battery_label'],
                        batch_item['has_box'],
                        batch_item['damage_pct']
                    )

                    if key not in seen_keys:
                        seen_keys.add(key)
                        unique_batch.append(batch_item)

                if unique_batch:
                    inserted = bulk_insert_prices(unique_batch)
                    success_count += inserted

                # Progress yangilash
                now = datetime.now()
                if (i % PROGRESS_UPDATE_INTERVAL == 0) or i == len(prices_data) - 1:
                    elapsed = (now - start_time).total_seconds()
                    speed = success_count / elapsed if elapsed > 0 else 0
                    remaining = (valid_count - i) / speed if speed > 0 else 0

                    progress_percent = ((i + 1) / valid_count) * 100
                    progress_bar = "█" * int(progress_percent / 5) + "░" * (20 - int(progress_percent / 5))

                    await safe_edit_message(
                        progress_msg,
                        f"💾 <b>Yuklanmoqda...</b>\n\n"
                        f"[{progress_bar}] {progress_percent:.1f}%\n\n"
                        f"✅ <b>{success_count:,}</b> / {valid_count:,}\n"
                        f"⚡ {speed:.0f} ta/sek\n"
                        f"🕐 ~{int(remaining)}s",
                        parse_mode="HTML"
                    )
                    last_update_time = now

                bulk_batch = []

        # ============================================
        # 8. YAKUNIY NATIJA
        # ============================================
        total_time = (datetime.now() - start_time).total_seconds()
        total_prices = get_total_prices_count()

        await message.answer(
            f"✅ <b>Import yakunlandi!</b>\n\n"
            f"📊 <b>Natijalar:</b>\n"
            f"• Jami qatorlar: {total_rows:,}\n"
            f"• O'tkazilgan: {skipped:,}\n"
            f"• Yuklandi: <b>{success_count:,}</b>\n"
            f"• Xatolar: {error_count:,}\n\n"
            f"💾 <b>Bazada jami:</b> {total_prices:,}\n"
            f"⏱ <b>Vaqt:</b> {int(total_time)}s ({total_time / 60:.1f} min)\n"
            f"⚡ <b>Tezlik:</b> {success_count / total_time:.0f} ta/sek",
            parse_mode="HTML",
            reply_markup=admin_kb()
        )

        await progress_msg.delete()

    except Exception as e:
        await message.answer(
            f"❌ <b>Xatolik:</b>\n\n"
            f"<code>{str(e)}</code>",
            parse_mode="HTML"
        )
        traceback.print_exc()

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

        await state.finish()


# ============================================
# TOZALASH
# ============================================

@dp.message_handler(lambda msg: msg.text == "🗑 Narxlarni tozalash", user_id=ADMINS)
async def cleanup_prices_start(message: types.Message):
    """Narxlarni tozalashni boshlash"""
    total = get_total_prices_count()

    await message.answer(
        f"⚠️ <b>Diqqat!</b>\n\n"
        f"Bazadagi <b>{total:,} ta narx</b> o'chiriladi!\n\n"
        f"Bu amalni qaytarib bo'lmaydi. Davom etasizmi?",
        parse_mode="HTML",
        reply_markup=cleanup_confirm_kb()
    )

    await CleanupState.confirm.set()


@dp.message_handler(state=CleanupState.confirm)
async def cleanup_confirm(message: types.Message, state: FSMContext):
    """Tozalashni tasdiqlash"""

    if message.text == "✅ Ha, tozalash":
        progress_msg = await message.answer("🔄 Tozalanmoqda...")

        try:
            if clear_all_prices():
                await progress_msg.edit_text(
                    "✅ <b>Barcha narxlar tozalandi!</b>",
                    parse_mode="HTML"
                )
            else:
                await progress_msg.edit_text("❌ Tozalashda xatolik!")
        except Exception as e:
            await progress_msg.edit_text(f"❌ Xato: {e}")

        await message.answer("Asosiy menu", reply_markup=admin_kb())
    else:
        await message.answer("Bekor qilindi.", reply_markup=admin_kb())

    await state.finish()


# ============================================
# STATISTIKA MENU - YANGI!
# ============================================

@dp.message_handler(lambda msg: msg.text == "📊 Statistika", user_id=ADMINS)
async def show_statistics_menu(message: types.Message):
    """Statistika menu - faqat adminlar uchun"""
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(text="🗄️ Database", callback_data="stats_database"),
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="stats_users")
    )
    keyboard.add(
        InlineKeyboardButton(text="📊 To'liq", callback_data="stats_full"),
        InlineKeyboardButton(text="📈 Batafsil", callback_data="stats_detailed")
    )

    await message.answer(
        "📊 <b>STATISTIKA MENU</b>\n\n"
        "Qaysi statistikani ko'rmoqchisiz?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ============================================
# DATABASE STATISTIKASI
# ============================================

@dp.callback_query_handler(lambda c: c.data == "stats_database", user_id=ADMINS)
async def show_database_statistics(callback: types.CallbackQuery):
    """Database statistikasi"""
    try:
        total_prices = get_total_prices_count()
        models = get_models()
        total_models = len(models)

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
        db_size = cursor.fetchone()[0]

        cursor.execute("""
            SELECT 
                schemaname,
                tablename,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
            LIMIT 5
        """)
        top_tables = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) 
            FROM pg_indexes 
            WHERE schemaname = 'public'
        """)
        total_indexes = cursor.fetchone()[0]

        cursor.execute("""
            SELECT 
                COUNT(*) as total_connections,
                COUNT(*) FILTER (WHERE state = 'active') as active_connections,
                COUNT(*) FILTER (WHERE state = 'idle') as idle_connections
            FROM pg_stat_activity
            WHERE datname = current_database()
        """)
        conn_stats = cursor.fetchone()

        cursor.close()
        conn.close()

        text = (
            f"🗄️ <b>DATABASE STATISTIKASI</b>\n\n"
            f"<b>PostgreSQL phones_db</b>\n"
            f"💾 Hajm: {db_size}\n"
            f"🔧 Indekslar: {total_indexes}\n\n"
            f"<b>📊 Ma'lumotlar:</b>\n"
            f"📱 Modellar: {total_models}\n"
            f"💰 Narxlar: {total_prices:,}\n\n"
            f"<b>🔌 Ulanishlar:</b>\n"
            f"  • Jami: {conn_stats[0]}\n"
            f"  • Aktiv: {conn_stats[1]}\n"
            f"  • Idle: {conn_stats[2]}\n\n"
            f"<b>📋 Top 5 jadvallar:</b>\n"
        )

        for schema, table, size in top_tables:
            text += f"  • <code>{table}</code>: {size}\n"

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        await callback.message.edit_text(f"❌ Xato: {e}")
        await callback.answer()


# ============================================
# FOYDALANUVCHILAR STATISTIKASI
# ============================================

@dp.callback_query_handler(lambda c: c.data == "stats_users", user_id=ADMINS)
async def show_users_statistics(callback: types.CallbackQuery):
    """Foydalanuvchilar statistikasi"""
    try:
        result = get_users_statistics()

        if not result['success']:
            await callback.message.edit_text(f"❌ Xato: {result.get('error')}")
            await callback.answer()
            return

        stats = result['stats']

        text = (
            f"👥 <b>FOYDALANUVCHILAR STATISTIKASI</b>\n\n"
            f"<b>📊 JAMI:</b>\n"
            f"  • Jami: {stats['total_users']:,}\n"
            f"  • Aktiv: {stats['total_active_users']:,} ({stats['active_percentage']}%)\n"
            f"  • Aktiv emas: {stats['total_inactive_users']:,}\n\n"
            f"<b>📅 BUGUNGI:</b>\n"
            f"  • Yangi userlar: {stats['today_new_users']}\n"
            f"  • Aktiv userlar: {stats['today_active_users']}\n\n"
            f"<b>📆 OYLIK:</b>\n"
            f"  • Yangi userlar: {stats['month_new_users']:,}\n"
            f"  • Aktiv userlar: {stats['month_active_users']:,}\n\n"
            f"<b>📱 QO'SHIMCHA:</b>\n"
            f"  • Telefon bor: {stats['users_with_phone']:,} ({stats['phone_percentage']}%)\n"
            f"  • Balans bor: {stats['users_with_balance']:,}\n"
            f"  • Bepul urinish bor: {stats['users_with_free_trials']:,}\n\n"
            f"⏰ <i>{result['timestamp']}</i>"
        )

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        await callback.message.edit_text(f"❌ Xato: {e}")
        await callback.answer()


# ============================================
# TO'LIQ STATISTIKA
# ============================================

@dp.callback_query_handler(lambda c: c.data == "stats_full", user_id=ADMINS)
async def show_full_statistics(callback: types.CallbackQuery):
    """To'liq statistika"""
    try:
        # Database
        total_prices = get_total_prices_count()
        models = get_models()
        total_models = len(models)

        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
        db_size = cursor.fetchone()[0]
        cursor.close()
        conn.close()

        # Users
        user_result = get_users_statistics()
        user_stats = user_result['stats'] if user_result['success'] else {}

        total_pricings = get_total_pricings()

        text = (
            f"📊 <b>TO'LIQ STATISTIKA</b>\n\n"
            f"<b>🗄️ DATABASE:</b>\n"
            f"  💾 Hajm: {db_size}\n"
            f"  📱 Modellar: {total_models}\n"
            f"  💰 Narxlar: {total_prices:,}\n\n"
            f"<b>👥 FOYDALANUVCHILAR:</b>\n"
            f"  • Jami: {user_stats.get('total_users', 0):,}\n"
            f"  • Aktiv: {user_stats.get('total_active_users', 0):,}\n"
            f"  • Bugungi yangi: {user_stats.get('today_new_users', 0)}\n"
            f"  • Oylik yangi: {user_stats.get('month_new_users', 0):,}\n\n"
            f"<b>📊 NARXLASHLAR:</b>\n"
            f"  • Jami: {total_pricings:,}\n"
            f"  • Bugungi aktiv: {user_stats.get('today_active_users', 0)}\n"
            f"  • Oylik aktiv: {user_stats.get('month_active_users', 0):,}\n\n"
            f"<b>💰 BALANS:</b>\n"
            f"  • Balans bor: {user_stats.get('users_with_balance', 0):,}\n"
            f"  • Bepul urinish bor: {user_stats.get('users_with_free_trials', 0):,}\n"
            f"  • Telefon bor: {user_stats.get('users_with_phone', 0):,}\n\n"
            f"⏰ <i>{user_result.get('timestamp', '')}</i>"
        )

        await callback.message.edit_text(text, parse_mode="HTML")
        await callback.answer()

    except Exception as e:
        await callback.message.edit_text(f"❌ Xato: {e}")
        await callback.answer()


# ============================================
# BATAFSIL STATISTIKA
# ============================================

@dp.callback_query_handler(lambda c: c.data == "stats_detailed", user_id=ADMINS)
async def show_detailed_statistics(callback: types.CallbackQuery):
    """Batafsil statistika"""
    try:
        result = get_detailed_users_statistics()

        if not result['success']:
            await callback.message.edit_text(f"❌ Xato: {result.get('error')}")
            await callback.answer()
            return

        stats = result['stats']

        # 1-xabar - Asosiy
        text1 = (
            f"📈 <b>BATAFSIL STATISTIKA</b>\n\n"
            f"<b>👥 FOYDALANUVCHILAR:</b>\n"
            f"  • Jami: {stats['total_users']:,}\n"
            f"  • Aktiv: {stats['total_active_users']:,} ({stats['active_percentage']}%)\n"
            f"  • Bugungi: {stats['today_new_users']}\n"
            f"  • Haftalik: {stats['week_new_users']:,}\n"
            f"  • Oylik: {stats['month_new_users']:,}\n\n"
            f"<b>📊 NARXLASHLAR:</b>\n"
            f"  • Jami: {stats['total_pricings']:,}\n"
            f"  • Bugungi: {stats['today_pricings']}\n"
            f"  • Oylik: {stats['month_pricings']:,}\n"
            f"  • Bepul: {stats['free_pricings']:,}\n"
            f"  • Pullik: {stats['paid_pricings']:,}\n\n"
            f"<b>💰 BALANS:</b>\n"
            f"  • Umumiy balans: {stats['total_balance']:,}\n"
            f"  • Umumiy bepul: {stats['total_free_trials']:,}\n\n"
            f"<b>💳 TO'LOVLAR:</b>\n"
            f"  • Jami: {stats['total_payments']}\n"
            f"  • Yakunlangan: {stats['completed_payments']}\n"
            f"  • Kutilayotgan: {stats['pending_payments']}\n"
            f"  • Summa: ${stats['total_paid_amount']:,.2f}"
        )

        await callback.message.edit_text(text1, parse_mode="HTML")

        # 2-xabar - Top userlar
        if stats.get('top_users'):
            text2 = "<b>🏆 TOP 5 AKTIV FOYDALANUVCHILAR:</b>\n\n"
            for i, user in enumerate(stats['top_users'][:5], 1):
                name = user['full_name'][:20]
                username = f"@{user['username']}" if user['username'] else ""
                text2 += (
                    f"{i}. <b>{name}</b> {username}\n"
                    f"   📊 Narxlashlar: {user['pricing_count']}\n"
                    f"   💰 Balans: {user['balance']}\n"
                    f"   🎁 Bepul: {user['free_trials_left']}\n\n"
                )
            await callback.message.answer(text2, parse_mode="HTML")

        # 3-xabar - Top telefonlar
        if stats.get('top_phone_models'):
            text3 = "<b>📱 TOP 5 TELEFON MODELLARI:</b>\n\n"
            for i, phone in enumerate(stats['top_phone_models'][:5], 1):
                text3 += f"{i}. <code>{phone['phone_model']}</code>\n"
                text3 += f"   Narxlashlar: {phone['count']}\n\n"
            await callback.message.answer(text3, parse_mode="HTML")

        # 4-xabar - Trend
        if stats.get('daily_trend'):
            text4 = "<b>📅 KUNLIK TREND (oxirgi 7 kun):</b>\n\n"
            for day in stats['daily_trend']:
                text4 += f"📆 {day['date']}: <b>{day['new_users']}</b> ta yangi user\n"
            text4 += f"\n⏰ <i>{result['timestamp']}</i>"
            await callback.message.answer(text4, parse_mode="HTML")

        await callback.answer()

    except Exception as e:
        await callback.message.edit_text(f"❌ Xato: {e}")
        await callback.answer()


# ============================================
# BEKOR QILISH
# ============================================

@dp.message_handler(state="*", commands=['cancel'])
@dp.message_handler(lambda msg: msg.text.lower() == 'bekor qilish', state="*")
async def cancel_handler(message: types.Message, state: FSMContext):
    """Har qanday jarayonni bekor qilish"""
    current_state = await state.get_state()

    if current_state is None:
        return

    await state.finish()
    await message.answer("Bekor qilindi.", reply_markup=admin_kb())