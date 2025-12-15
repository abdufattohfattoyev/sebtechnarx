# app.py - ASOSIY FAYL
import logging
from aiogram import executor

from loader import dp, bot
import middlewares, filters, handlers
from data.config import ADMINS

# Logging sozlamasi
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


# Bot ishga tushganda
async def on_startup(dispatcher):
    """Bot ishga tushganda bajariladigan funksiyalar"""

    # 1. Asosiy database yaratish (PHONES.DB)
    try:
        from utils.db_api.database import init_db
        init_db()
        logging.info("✅ phones.db yaratildi yoki ulandi")
    except Exception as e:
        logging.error(f"❌ phones.db xato: {e}")

    # 2. Statistika database yaratish (STATS.DB)
    try:
        from utils.db_api.stats_database import init_stats_tables
        init_stats_tables()
        logging.info("✅ stats.db yaratildi!")
    except Exception as e:
        logging.error(f"❌ stats.db xato: {e}")

    # 3. Adminlarga xabar yuborish
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, "🤖 Bot ishga tushdi!")
        except Exception as e:
            logging.error(f"❌ Admin {admin_id} ga xabar yuborib bo'lmadi: {e}")

    logging.info("🚀 Bot muvaffaqiyatli ishga tushdi!")


# Bot to'xtaganda
async def on_shutdown(dispatcher):
    """Bot to'xtaganda bajariladigan funksiyalar"""

    # Adminlarga xabar yuborish
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, "⛔ Bot to'xtatildi!")
        except:
            pass

    logging.warning("⛔ Bot to'xtatildi!")

    # Connection'larni yopish
    await bot.close()


if __name__ == '__main__':
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )