# """
# ADMIN PANEL HANDLERS - Bot ichida statistika ko'rish
# """
# from aiogram import types
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# from loader import dp
# from data.config import ADMINS
# from utils.db_api.stats_database import (
#     get_conn, get_global_stats, get_daily_stats
# )
# import traceback
#
#
# def admin_main_menu():
#     """Admin asosiy menu"""
#     kb = InlineKeyboardMarkup(row_width=1)
#     kb.add(
#         InlineKeyboardButton("📊 Database ma'lumotlar", callback_data="admin:db_info"),
#         InlineKeyboardButton("👥 TOP foydalanuvchilar", callback_data="admin:top_users"),
#         InlineKeyboardButton("📱 TOP modellar", callback_data="admin:top_models"),
#         InlineKeyboardButton("📈 7 kunlik statistika", callback_data="admin:daily_stats"),
#         InlineKeyboardButton("🌍 Umumiy statistika", callback_data="admin:global_stats"),
#         InlineKeyboardButton("❌ Yopish", callback_data="admin:close")
#     )
#     return kb
#
#
# @dp.message_handler(commands=['admin'], user_id=ADMINS)
# async def admin_panel_command(message: types.Message):
#     """Admin panel komandasi"""
#     text = "🔐 <b>ADMIN PANEL</b>\n\n"
#     text += "Kerakli bo'limni tanlang:"
#
#     await message.answer(
#         text,
#         reply_markup=admin_main_menu(),
#         parse_mode='HTML'
#     )
#
#
# @dp.message_handler(lambda message: message.text == "🔐 Admin panel", user_id=ADMINS)
# async def admin_panel_button(message: types.Message):
#     """Admin panel tugmasi"""
#     text = "🔐 <b>ADMIN PANEL</b>\n\n"
#     text += "Kerakli bo'limni tanlang:"
#
#     await message.answer(
#         text,
#         reply_markup=admin_main_menu(),
#         parse_mode='HTML'
#     )
#
#
# @dp.callback_query_handler(lambda c: c.data and c.data.startswith('admin:'), user_id=ADMINS)
# async def admin_callback_handler(callback: types.CallbackQuery):
#     """Admin callback handler"""
#     await callback.answer()
#
#     data = callback.data
#
#     try:
#         if data == "admin:db_info":
#             await show_db_info(callback)
#
#         elif data == "admin:top_users":
#             await show_top_users(callback)
#
#         elif data == "admin:top_models":
#             await show_top_models(callback)
#
#         elif data == "admin:daily_stats":
#             await show_daily_stats_admin(callback)
#
#         elif data == "admin:global_stats":
#             await show_global_stats_admin(callback)
#
#         elif data == "admin:close":
#             await callback.message.delete()
#
#         elif data == "admin:back":
#             text = "🔐 <b>ADMIN PANEL</b>\n\n"
#             text += "Kerakli bo'limni tanlang:"
#             await callback.message.edit_text(
#                 text,
#                 reply_markup=admin_main_menu(),
#                 parse_mode='HTML'
#             )
#
#     except Exception as e:
#         print(f"❌ Admin panel xato: {e}")
#         print(traceback.format_exc())
#         await callback.message.answer("❌ Xatolik yuz berdi")
#
#
# async def show_db_info(callback: types.CallbackQuery):
#     """Database umumiy ma'lumotlar"""
#     conn = get_conn()
#     c = conn.cursor()
#
#     # Jami foydalanuvchilar
#     c.execute("SELECT COUNT(*) as count FROM users")
#     total_users = c.fetchone()['count']
#
#     # Jami narxlatishlar
#     c.execute("SELECT COUNT(*) as count FROM price_history")
#     total_inquiries = c.fetchone()['count']
#
#     # Jami modellar
#     c.execute("SELECT COUNT(DISTINCT model_name) as count FROM price_history")
#     total_models = c.fetchone()['count']
#
#     # Bugungi faollik
#     c.execute("SELECT COUNT(*) as count FROM price_history WHERE DATE(created_at) = DATE('now')")
#     today_count = c.fetchone()['count']
#
#     # Oxirgi 24 soatdagi faollik
#     c.execute("SELECT COUNT(*) as count FROM price_history WHERE created_at >= datetime('now', '-1 day')")
#     last_24h = c.fetchone()['count']
#
#     # Bugungi faol foydalanuvchilar
#     c.execute("""
#         SELECT COUNT(DISTINCT user_id) as count
#         FROM price_history
#         WHERE DATE(created_at) = DATE('now')
#     """)
#     today_users = c.fetchone()['count']
#
#     conn.close()
#
#     text = "📊 <b>DATABASE MA'LUMOTLAR</b>\n\n"
#     text += f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
#     text += f"🔢 Jami narxlatishlar: <b>{total_inquiries}</b>\n"
#     text += f"📱 Turli modellar: <b>{total_models}</b>\n\n"
#     text += f"📅 <b>BUGUN:</b>\n"
#     text += f"  • {today_count} ta narxlatish\n"
#     text += f"  • {today_users} faol foydalanuvchi\n\n"
#     text += f"🕐 <b>Oxirgi 24 soat:</b> {last_24h} ta"
#
#     kb = InlineKeyboardMarkup()
#     kb.add(
#         InlineKeyboardButton("🔄 Yangilash", callback_data="admin:db_info"),
#         InlineKeyboardButton("◀️ Orqaga", callback_data="admin:back")
#     )
#
#     await callback.message.edit_text(
#         text,
#         reply_markup=kb,
#         parse_mode='HTML'
#     )
#
#
# async def show_top_users(callback: types.CallbackQuery):
#     """TOP foydalanuvchilar"""
#     conn = get_conn()
#     c = conn.cursor()
#
#     c.execute("""
#         SELECT
#             u.username,
#             u.first_name,
#             COUNT(ph.id) as total_inquiries,
#             COUNT(DISTINCT DATE(ph.created_at)) as active_days
#         FROM users u
#         LEFT JOIN price_history ph ON u.id = ph.user_id
#         GROUP BY u.id
#         HAVING total_inquiries > 0
#         ORDER BY total_inquiries DESC
#         LIMIT 10
#     """)
#
#     users = [dict(row) for row in c.fetchall()]
#     conn.close()
#
#     text = "👥 <b>TOP 10 FOYDALANUVCHILAR</b>\n\n"
#
#     if not users:
#         text += "❌ Ma'lumot yo'q"
#     else:
#         for i, user in enumerate(users, 1):
#             username = user['username'] or '-'
#             first_name = user['first_name'] or 'Anonim'
#
#             if i == 1:
#                 emoji = "🥇"
#             elif i == 2:
#                 emoji = "🥈"
#             elif i == 3:
#                 emoji = "🥉"
#             else:
#                 emoji = f"{i}."
#
#             text += f"{emoji} <b>{first_name}</b> (@{username})\n"
#             text += f"    📊 {user['total_inquiries']} ta narxlatish\n"
#             text += f"    📅 {user['active_days']} faol kun\n\n"
#
#     kb = InlineKeyboardMarkup()
#     kb.add(
#         InlineKeyboardButton("🔄 Yangilash", callback_data="admin:top_users"),
#         InlineKeyboardButton("◀️ Orqaga", callback_data="admin:back")
#     )
#
#     await callback.message.edit_text(
#         text,
#         reply_markup=kb,
#         parse_mode='HTML'
#     )
#
#
# async def show_top_models(callback: types.CallbackQuery):
#     """TOP modellar"""
#     conn = get_conn()
#     c = conn.cursor()
#
#     c.execute("""
#         SELECT
#             model_name,
#             COUNT(*) as total_inquiries,
#             COUNT(DISTINCT user_id) as unique_users
#         FROM price_history
#         GROUP BY model_name
#         ORDER BY total_inquiries DESC
#         LIMIT 10
#     """)
#
#     models = [dict(row) for row in c.fetchall()]
#     conn.close()
#
#     text = "📱 <b>TOP 10 MODELLAR</b>\n\n"
#
#     if not models:
#         text += "❌ Ma'lumot yo'q"
#     else:
#         for i, model in enumerate(models, 1):
#             if i == 1:
#                 emoji = "🥇"
#             elif i == 2:
#                 emoji = "🥈"
#             elif i == 3:
#                 emoji = "🥉"
#             else:
#                 emoji = f"{i}."
#
#             text += f"{emoji} <b>{model['model_name']}</b>\n"
#             text += f"    📊 {model['total_inquiries']} ta so'rov\n"
#             text += f"    👥 {model['unique_users']} foydalanuvchi\n\n"
#
#     kb = InlineKeyboardMarkup()
#     kb.add(
#         InlineKeyboardButton("🔄 Yangilash", callback_data="admin:top_models"),
#         InlineKeyboardButton("◀️ Orqaga", callback_data="admin:back")
#     )
#
#     await callback.message.edit_text(
#         text,
#         reply_markup=kb,
#         parse_mode='HTML'
#     )
#
#
# async def show_daily_stats_admin(callback: types.CallbackQuery):
#     """7 kunlik statistika"""
#     stats = get_daily_stats(days=7)
#
#     text = "📈 <b>7 KUNLIK STATISTIKA</b>\n\n"
#
#     if not stats:
#         text += "❌ Ma'lumot yo'q"
#     else:
#         max_count = max([s['count'] for s in stats]) if stats else 1
#
#         for item in stats:
#             # Grafik chizish
#             bar_length = int((item['count'] / max_count) * 15) if max_count > 0 else 1
#             bars = "▓" * bar_length
#
#             text += f"<b>{item['date']}</b>\n"
#             text += f"{bars} {item['count']} ta\n"
#             text += f"👥 {item['users']} foydalanuvchi\n\n"
#
#     kb = InlineKeyboardMarkup()
#     kb.add(
#         InlineKeyboardButton("🔄 Yangilash", callback_data="admin:daily_stats"),
#         InlineKeyboardButton("◀️ Orqaga", callback_data="admin:back")
#     )
#
#     await callback.message.edit_text(
#         text,
#         reply_markup=kb,
#         parse_mode='HTML'
#     )
#
#
# async def show_global_stats_admin(callback: types.CallbackQuery):
#     """Umumiy statistika"""
#     kb = InlineKeyboardMarkup(row_width=2)
#     kb.add(
#         InlineKeyboardButton("📅 Bugun", callback_data="admin:global:today"),
#         InlineKeyboardButton("📆 Hafta", callback_data="admin:global:week"),
#         InlineKeyboardButton("📊 Oy", callback_data="admin:global:month"),
#         InlineKeyboardButton("📈 Hammasi", callback_data="admin:global:all")
#     )
#     kb.add(InlineKeyboardButton("◀️ Orqaga", callback_data="admin:back"))
#
#     text = "🌍 <b>UMUMIY STATISTIKA</b>\n\n"
#     text += "Davrni tanlang:"
#
#     await callback.message.edit_text(
#         text,
#         reply_markup=kb,
#         parse_mode='HTML'
#     )
#
#
# @dp.callback_query_handler(lambda c: c.data and c.data.startswith('admin:global:'), user_id=ADMINS)
# async def show_global_stats_period(callback: types.CallbackQuery):
#     """Umumiy statistika - davr"""
#     await callback.answer()
#
#     period = callback.data.split(":")[-1]
#     stats = get_global_stats(period)
#
#     period_names = {
#         'today': 'BUGUN',
#         'week': 'SHU HAFTA',
#         'month': 'SHU OY',
#         'all': 'BARCHA VAQT'
#     }
#
#     text = f"🌍 <b>UMUMIY STATISTIKA - {period_names[period]}</b>\n\n"
#     text += f"🔢 Jami narxlatishlar: <b>{stats['total_inquiries']}</b>\n"
#     text += f"👥 Faol foydalanuvchilar: <b>{stats['active_users']}</b>\n"
#     text += f"📱 Turli modellar: <b>{stats['unique_models']}</b>\n"
#
#     if stats.get('top_models'):
#         text += f"\n<b>🏆 TOP 5 modellar:</b>\n"
#         for i, model in enumerate(stats['top_models'][:5], 1):
#             text += f"{i}. {model['model_name']} - {model['count']} marta\n"
#
#     kb = InlineKeyboardMarkup(row_width=2)
#     kb.add(
#         InlineKeyboardButton("📅 Bugun", callback_data="admin:global:today"),
#         InlineKeyboardButton("📆 Hafta", callback_data="admin:global:week"),
#         InlineKeyboardButton("📊 Oy", callback_data="admin:global:month"),
#         InlineKeyboardButton("📈 Hammasi", callback_data="admin:global:all")
#     )
#     kb.add(InlineKeyboardButton("◀️ Orqaga", callback_data="admin:back"))
#
#     await callback.message.edit_text(
#         text,
#         reply_markup=kb,
#         parse_mode='HTML'
#     )