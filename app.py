# app.py - PostgreSQL VERSION
import logging
import asyncio
from aiogram import executor
from aiogram.utils.exceptions import TelegramAPIError, NetworkError

from loader import dp, bot
import middlewares, filters, handlers
from data.config import ADMINS, USE_WEBHOOK, WEBHOOK_URL, WEBHOOK_PATH, WEBAPP_HOST, WEBAPP_PORT

# ============================================
# LOGGING KONFIGURATSIYASI
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


async def on_startup(dispatcher):
    """Bot ishga tushganda"""
    # ── Bot API HTTP server (Django uchun) ──────────────────
    try:
        from data.config import BOT_API_PORT
        from utils.bot_api import start_bot_api
        start_bot_api(BOT_API_PORT)
    except Exception as e:
        logger.warning(f"⚠️ Bot API server ishga tushmadi: {e}")
    if USE_WEBHOOK:
        await bot.set_webhook(WEBHOOK_URL)
        logger.info(f"✅ Webhook o'rnatildi: {WEBHOOK_URL}")

    logger.info("=" * 60)
    logger.info("🚀 BOT ISHGA TUSHMOQDA...")
    logger.info("=" * 60)

    # ============================================
    # 1. POSTGRESQL PHONES DATABASE
    # ============================================
    try:
        from utils.db_api.database import init_db, test_connection

        # Avval ulanishni tekshirish
        logger.info("🔄 PostgreSQL ga ulanish tekshirilmoqda...")
        if test_connection():
            logger.info("✅ PostgreSQL ulanishi muvaffaqiyatli!")

            # Database yaratish
            logger.info("🔄 Database strukturasi tekshirilmoqda...")
            init_db()
            logger.info("✅ phones_db tayyor!")
        else:
            logger.error("❌ PostgreSQL ga ulanib bo'lmadi!")
            logger.error("⚠️ .env faylni tekshiring!")
            raise Exception("PostgreSQL connection failed")

    except ImportError as e:
        logger.error(f"❌ database_postgres.py topilmadi: {e}")
        logger.error("📁 utils/db_api/ papkasida database_postgres.py borligini tekshiring")
        raise
    except Exception as e:
        logger.error(f"❌ phones_db xato: {e}")
        logger.error("💡 PostgreSQL ishlab turganini tekshiring:")
        logger.error("   sudo systemctl status postgresql")
        raise

    # ============================================
    # 2. USER STATISTICS DATABASE (ixtiyoriy)
    # ============================================
    try:
        from utils.db_api.user_database import init_user_db
        init_user_db()
        logger.info("✅ stats.db yaratildi!")
    except ImportError:
        logger.warning("⚠️ user_database.py topilmadi, statistika o'chirilgan")
    except Exception as e:
        logger.warning(f"⚠️ stats.db xato (kritik emas): {e}")

    # ============================================
    # 3. ADMINLARGA XABAR YUBORISH
    # ============================================
    logger.info("📨 Adminlarga xabar yuborilmoqda...")
    success_count = 0

    for admin_id in ADMINS:
        try:
            await asyncio.wait_for(
                bot.send_message(
                    admin_id,
                    "🤖 <b>Bot ishga tushdi!</b>\n\n"
                    "🗄️ Database: PostgreSQL\n"
                    "📊 Status: Tayyor",
                    parse_mode="HTML"
                ),
                timeout=10
            )
            success_count += 1
            logger.info(f"✅ Admin {admin_id} ga xabar yuborildi")
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Admin {admin_id} ga xabar yuborish timeout")
        except (TelegramAPIError, NetworkError) as e:
            logger.warning(f"⚠️ Admin {admin_id} ga ulanib bo'lmadi: {e}")
        except Exception as e:
            logger.error(f"❌ Admin {admin_id} ga xabar yuborishda xato: {e}")

    logger.info(f"📨 {success_count}/{len(ADMINS)} ta adminga xabar yuborildi")

    # ============================================
    # 4. YAKUNIY XABAR
    # ============================================
    logger.info("=" * 60)
    logger.info("✅ BOT MUVAFFAQIYATLI ISHGA TUSHDI!")
    logger.info("🗄️  Database: PostgreSQL")
    logger.info("📊 Polling: Faol")
    logger.info("=" * 60)


async def on_shutdown(dispatcher):
    """Bot to'xtaganda"""

    logger.warning("=" * 60)
    logger.warning("⛔ BOT TO'XTATILMOQDA...")
    logger.warning("=" * 60)

    # ============================================
    # 1. ADMINLARGA XABAR
    # ============================================
    for admin_id in ADMINS:
        try:
            await asyncio.wait_for(
                bot.send_message(
                    admin_id,
                    "⛔ <b>Bot to'xtatildi!</b>",
                    parse_mode="HTML"
                ),
                timeout=5
            )
        except asyncio.TimeoutError:
            logger.warning(f"⚠️ Admin {admin_id} ga shutdown xabari timeout")
        except (TelegramAPIError, NetworkError) as e:
            logger.warning(f"⚠️ Admin {admin_id} ga shutdown xabari yuborilmadi: {e}")
        except Exception as e:
            logger.error(f"❌ Admin {admin_id} ga shutdown xabarida kutilmagan xato: {e}")
            # Jiddiy xato — boshqa adminlarga xabar berish
            for other_admin in ADMINS:
                if other_admin != admin_id:
                    try:
                        await asyncio.wait_for(
                            bot.send_message(
                                other_admin,
                                f"❌ <b>Shutdown xatosi!</b>\nAdmin {admin_id}: {e}",
                                parse_mode="HTML"
                            ),
                            timeout=5
                        )
                    except Exception:
                        pass

    # ============================================
    # 2. CONNECTION'LARNI YOPISH
    # ============================================
    logger.info("🔄 Connection'lar yopilmoqda...")

    try:
        await bot.close()
        logger.info("✅ Bot connection yopildi")
    except Exception as e:
        logger.error(f"❌ Bot connection yopishda xato: {e}")

    # PostgreSQL connection'larni yopish kerak emas
    # Chunki har bir funksiya o'z connection'ini ochadi va yopadi

    logger.warning("=" * 60)
    logger.warning("✅ BOT TO'LIQ TO'XTATILDI!")
    logger.warning("=" * 60)


def main():
    """Bot ishga tushirish — webhook yoki polling"""
    try:
        if USE_WEBHOOK:
            logger.info(f"🚀 Webhook rejimida ishga tushmoqda: {WEBHOOK_URL}")
            executor.start_webhook(
                dispatcher=dp,
                webhook_path=WEBHOOK_PATH,
                on_startup=on_startup,
                on_shutdown=on_shutdown,
                skip_updates=True,
                host=WEBAPP_HOST,
                port=WEBAPP_PORT,
            )
        else:
            logger.info("🚀 Polling rejimida ishga tushmoqda...")
            executor.start_polling(
                dp,
                on_startup=on_startup,
                on_shutdown=on_shutdown,
                skip_updates=True,
                timeout=60,
                relax=0.1,
                fast=False,
            )

    except (KeyboardInterrupt, SystemExit):
        logger.info("✋ Bot to'xtatildi (Ctrl+C)")

    except Exception as e:
        logger.critical("=" * 60)
        logger.critical(f"💥 KRITIK XATO: {e}")
        logger.critical("=" * 60)

        # Xatolik tafsilotlarini yozish
        import traceback
        logger.critical(traceback.format_exc())

        raise


if __name__ == '__main__':
    main()