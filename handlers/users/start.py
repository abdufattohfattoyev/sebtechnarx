# handlers/users/start.py - MAJBURIY OBUNA BILAN TO'LIQ VERSIYA ⚡

import asyncio
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import MessageNotModified

from handlers.users.payment import PaymentState
from loader import dp, bot
from keyboards.default.knopkalar import (
    main_menu, create_keyboard,
    create_parts_inline_kb,
    balance_menu_kb, admin_kb, phone_request_kb
)
from keyboards.inline.payment_keyboards import (
    create_tariffs_inline_keyboard,
    create_payment_inline_keyboard
)
from data.config import ADMINS, FREE_TRIALS_DEFAULT
from utils.misc.maintenance import get_maintenance_status, is_feature_enabled

# ⭐ MAJBURIY OBUNA IMPORT
from .subscription import (
    check_subscription,
    subscription_keyboard,
    SUBSCRIPTION_TEXT,
    CHANNEL_USERNAME
)

from utils.api import api
from utils.db_api.database import get_models, get_storages, get_colors, get_batteries, get_price
from utils.db_api.user_database import (
    check_can_price,
    create_user,
    get_user_balance,
    use_pricing as use_pricing_local,
    update_phone_number,
    get_user_payment_history,
)

# ================ CONSTANTS ================
logger = logging.getLogger(__name__)

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

TELEGRAM_CHANNEL = "https://t.me/sebtech1"
INSTAGRAM_LINK = "https://www.instagram.com/sebtech.uz"
CALL_CENTER_1 = "+998(77)-285-99-99"
CALL_CENTER_2 = "+998(91)-285-99-99"

ABOUT_TEXT = f"""✨ <b>SEPTECH</b>

<i>Bozorni his qiladigan narx. Qarorni oson qiladigan standart.</i>

📌 <b>SEPTECH Narxlash Boti</b> — <b>Xurshed Tilloyev</b> tashabbusi bilan yaratilgan premium tizim.
Real savdo tajribasi + bozor tahlillari asosida ishlaydi.

<b>Nima beradi?</b>
- real bozor qiymati (model / xotira / holat bo'yicha)
- adolatli, tushunarli standart
- <b>inson aralashuvisiz</b> — faqat algoritm

🔎 <b>Eslatma:</b> narx bozor bilan birga o'zgaradi, algoritm esa barcha uchun bir xil.

<b>Qadriyatlar:</b> Shaffoflik • Aniqlik • Ishonch

📣 <b>Rasmiy sahifalar:</b>
- Telegram: <a href="{TELEGRAM_CHANNEL}">Telegram Kanal</a>
- Instagram: <a href="{INSTAGRAM_LINK}">Instagram Sahifa</a>

📞 <b>Call-center:</b>
- {CALL_CENTER_1}
- {CALL_CENTER_2}

<i>SEPTECH — telefon narxining yangi standarti.</i>
"""


# ================ STATES ================
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


# ================ HELPER FUNCTIONS ================
def uz_now():
    """Tashkent vaqti"""
    return datetime.now(ZoneInfo("Asia/Tashkent")).strftime("%d.%m.%Y %H:%M")


def should_ask_sim_type(model_name: str) -> bool:
    """iPhone 14+ uchun SIM so'rash"""
    if not model_name:
        return False
    match = re.search(r'iphone\s+(\d+)', model_name.lower())
    return match and int(match.group(1)) >= 14


def calculate_final_price(data: dict) -> str:
    """Yakuniy narx hisoblash"""
    try:
        selected_parts = data.get('selected_parts', [])
        damage = "Yangi" if not selected_parts else "+".join(sorted(selected_parts))

        price = get_price(
            model_id=data.get('model_id'),
            storage=data.get('storage', ''),
            color=data.get('color', ''),
            sim_type=data.get('sim_type', 'physical'),
            battery=data.get('battery', '100%'),
            has_box=data.get('has_box', 'Yo\'q'),
            damage=damage
        )

        if price:
            return f"{price:,.0f} $".replace(",", " ") if isinstance(price, (int, float)) else str(price)

        # Fallback
        base_price = get_price(
            model_id=data.get('model_id'),
            storage=data.get('storage', ''),
            color=data.get('color', ''),
            sim_type=data.get('sim_type', 'physical'),
            battery=data.get('battery', '100%'),
            has_box=data.get('has_box', 'Yo\'q'),
            damage="Yangi"
        )

        if base_price and isinstance(base_price, (int, float)):
            discount = sum([0.02, 0.03, 0.05, 0.04, 0.08, 0.05, 0.10, 0.06][i]
                           for i, p in enumerate(
                ['battery', 'back_cover', 'face_id', 'glass', 'screen', 'camera', 'broken', 'body'])
                           if p in selected_parts)
            final = base_price * (1 - min(discount, 0.25))
            return f"{final:,.0f} $".replace(",", " ")

        return "Narx topilmadi"
    except Exception as e:
        logger.error(f"Price calculation error: {e}")
        return "Hisoblash xatosi"


def sort_models_naturally(models):
    """Modellarni tartibga solish"""

    def extract_info(name):
        lower = name.lower()
        if 'xs max' in lower: return (10.5, 2)
        if 'xs' in lower: return (10.5, 1)
        if 'xr' in lower: return (10.3, 0)
        if lower.endswith(' x'): return (10, 0)

        match = re.search(r'iphone\s+(\d+)', lower)
        if match:
            num = int(match.group(1))
            pri = 3 if 'pro max' in lower or 'plus' in lower else 2 if 'pro' in lower else 1 if 'mini' in lower else 0
            return (num, pri)
        return (0, 0)

    return sorted(models, key=lambda x: extract_info(x['name']), reverse=True)


def sort_storages_naturally(storages):
    """Xotiralarni tartibga solish"""

    def extract_size(s):
        match = re.search(r'(\d+)', s)
        return int(match.group(1)) if match else 0

    return sorted(storages, key=lambda x: extract_size(x['size']), reverse=True)


def sort_batteries_naturally(batteries):
    """Batareyalarni tartibga solish"""

    def extract_percent(l):
        match = re.search(r'(\d+)', l)
        return int(match.group(1)) if match else 0

    return sorted(batteries, key=lambda x: extract_percent(x['label']), reverse=True)


def parts_choice_kb():
    """Qismlar tanlash tugmalari"""
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Ha"), KeyboardButton("❌ Yo'q"))
    kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
    return kb


async def auto_check_payment(order_id: str, user_id: int, state: FSMContext):
    """Avtomatik to'lov tekshirish"""
    try:
        await asyncio.sleep(10)
        current_state = await state.get_state()
        if current_state != PaymentState.waiting_check.state:
            return

        result = await api.check_payment_status(order_id)
        if result.get('success') and result.get('has_payment') and result.get('state') == 2:
            text = f"""✅ <b>TO'LOV MUVAFFAQIYATLI!</b>

💰 <b>Balans:</b> {result.get('balance', 0)} ta
📦 <b>Qo'shildi:</b> {result.get('count', 0)} ta
💵 <b>Summa:</b> {result.get('amount', 0):,.0f} so'm

🎉 Endi narxlashingiz mumkin!
"""
            await bot.send_message(user_id, text, parse_mode="HTML")
            await state.finish()
    except Exception as e:
        logger.error(f"Auto check error: {e}")


# ================ START HANDLER (⭐ MAJBURIY OBUNA BILAN) ================
@dp.message_handler(commands=['start'], state='*')
async def start(message: types.Message, state: FSMContext):
    """
    Start handler - MAJBURIY OBUNA BILAN (TO'LIQ TUZATILGAN)
    """
    await state.finish()
    user = message.from_user

    # ============================================================
    # ⭐ 1. OBUNA TEKSHIRISH (Adminlar uchun yo'q)
    # ============================================================
    if user.id not in ADMINS:
        is_subscribed = await check_subscription(user.id)

        if not is_subscribed:
            # Obuna yo'q - obuna xabarini yuborish
            await message.answer(
                SUBSCRIPTION_TEXT,
                reply_markup=subscription_keyboard(),
                parse_mode="HTML"
            )
            return  # ⚠️ To'xtatish - obuna bo'lmaguncha davom etmaydi

    # ============================================================
    # ⭐ 2. USER YARATISH/YANGILASH (API + LOCAL)
    # ============================================================
    try:
        # API dan user yaratish/olish
        api_task = api.create_user(
            user.id,
            user.full_name or f"User{user.id}",
            user.username or ""
        )

        # Local database ga user yaratish/yangilash
        local_task = asyncio.to_thread(
            create_user,
            user.id,
            user.full_name or f"User{user.id}",
            user.username or "",
            None  # phone_number
        )

        # Parallel bajarish
        api_result, local_result = await asyncio.gather(
            api_task,
            local_task,
            return_exceptions=True
        )

        # API xatosi
        if isinstance(api_result, Exception):
            logger.error(f"API error in start: {api_result}")
            await message.answer(
                "❌ Server bilan aloqa yo'q. Iltimos qaytadan /start bosing.",
                parse_mode="HTML"
            )
            return

        # Local DB xatosi (lekin davom etamiz)
        if isinstance(local_result, Exception):
            logger.error(f"Local DB error in start: {local_result}")

        # ============================================================
        # ⭐ 3. MA'LUMOTLARNI OLISH
        # ============================================================

        # API dan ma'lumotlar
        phone = api_result.get('phone')
        api_balance = int(api_result.get('balance', 0))

        # Local dan bepul urinishlarni olish
        free_trials = FREE_TRIALS_DEFAULT  # Default
        local_balance = 0

        try:
            local_data = get_user_balance(user.id)
            if local_data.get('success'):
                free_trials = int(local_data.get('free_trials_left', FREE_TRIALS_DEFAULT))
                local_balance = int(local_data.get('balance', 0))
        except Exception as e:
            logger.warning(f"Failed to get local balance: {e}")

        # Balanslarni birlashtirish
        total_balance = api_balance + local_balance

        # ============================================================
        # ⭐ 4. TELEFON RAQAMNI LOKAL BAZAGA SINXLASH
        # ============================================================
        if phone and not isinstance(local_result, Exception):
            try:
                await asyncio.to_thread(
                    update_phone_number,
                    user.id,
                    phone
                )
                logger.info(f"Phone synced for user {user.id}")
            except Exception as e:
                logger.warning(f"Phone sync failed: {e}")

    except Exception as e:
        logger.error(f"Critical error in start handler: {e}", exc_info=True)
        await message.answer(
            "❌ Xatolik yuz berdi. Iltimos qaytadan /start bosing.",
            parse_mode="HTML"
        )
        return

    # ============================================================
    # ⭐ 5. TELEFON RAQAM TEKSHIRISH
    # ============================================================
    if not phone:
        # Telefon raqam yo'q - so'rash
        welcome_text = f"""👋 <b>{user.full_name}</b>!

📱 <b>iPhone narxlash botiga xush kelibsiz!</b>

🎁 <b>Bepul urinishlar:</b> {free_trials} ta
💰 <b>Pullik balans:</b> {total_balance} ta

📞 <b>Telefon raqamingizni yuboring:</b>
<i>(Tugmani bosib yoki +998 XX XXX XX XX formatida yuboring)</i>"""

        await UserState.waiting_phone.set()
        await message.answer(
            welcome_text,
            reply_markup=phone_request_kb(),
            parse_mode="HTML"
        )
        return

    # ============================================================
    # ⭐ 6. BOSH MENYU KO'RSATISH
    # ============================================================
    welcome_text = f"""👋 <b>Assalomu alaykum, {user.full_name}!</b>

📱 <b>iPhone narxlash botiga xush kelibsiz!</b>

💳 <b>Balanslaringiz:</b>
🎁 Bepul: <b>{free_trials}</b> ta
💰 Pullik: <b>{total_balance}</b> ta

⬇️ <b>Quyidagi tugmalardan birini tanlang:</b>"""

    await message.answer(
        welcome_text,
        reply_markup=main_menu(user.id in ADMINS),
        parse_mode="HTML"
    )


# ================ OBUNA CALLBACK HANDLER (⭐ TO'LIQ TUZATILGAN) ================
@dp.callback_query_handler(lambda c: c.data == "check_subscription", state="*")
async def check_subscription_callback(call: types.CallbackQuery, state: FSMContext):
    """
    Obuna tekshirish callback - TO'LIQ TUZATILGAN
    """
    await call.answer("🔄 Tekshirilmoqda...")

    user = call.from_user
    is_subscribed = await check_subscription(user.id)

    if is_subscribed:
        # ✅ OBUNA BO'LGAN

        # Obuna xabarini o'chirish
        try:
            await call.message.delete()
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")

        # ============================================================
        # ⭐ USER YARATISH (start handlerdan nusxalangan logic)
        # ============================================================
        try:
            # API va Local parallel
            api_task = api.create_user(
                user.id,
                user.full_name or f"User{user.id}",
                user.username or ""
            )

            local_task = asyncio.to_thread(
                create_user,
                user.id,
                user.full_name or f"User{user.id}",
                user.username or "",
                None
            )

            api_result, local_result = await asyncio.gather(
                api_task,
                local_task,
                return_exceptions=True
            )

            # API xatosi
            if isinstance(api_result, Exception):
                logger.error(f"API error after subscription: {api_result}")
                await call.message.answer(
                    "❌ Server bilan aloqa yo'q. Iltimos /start bosing.",
                    parse_mode="HTML"
                )
                return

            # Ma'lumotlarni olish
            phone = api_result.get('phone')
            api_balance = int(api_result.get('balance', 0))

            free_trials = FREE_TRIALS_DEFAULT
            local_balance = 0

            try:
                local_data = get_user_balance(user.id)
                if local_data.get('success'):
                    free_trials = int(local_data.get('free_trials_left', FREE_TRIALS_DEFAULT))
                    local_balance = int(local_data.get('balance', 0))
            except:
                pass

            total_balance = api_balance + local_balance

            # Phone sinxlash
            if phone and not isinstance(local_result, Exception):
                try:
                    await asyncio.to_thread(update_phone_number, user.id, phone)
                except:
                    pass

        except Exception as e:
            logger.error(f"Error after subscription check: {e}")
            await call.message.answer(
                "❌ Xatolik. Iltimos /start bosing.",
                parse_mode="HTML"
            )
            return

        # ============================================================
        # ⭐ MUVAFFAQIYAT XABARI
        # ============================================================

        # Telefon yo'q bo'lsa
        if not phone:
            success_text = f"""✅ <b>Obuna tasdiqlandi!</b>

🎉 Endi botdan to'liq foydalanishingiz mumkin!

💳 <b>Balanslaringiz:</b>
🎁 Bepul: <b>{free_trials}</b> ta
💰 Pullik: <b>{total_balance}</b> ta

📞 <b>Telefon raqamingizni yuboring:</b>
<i>(Tugmani bosib yoki +998 XX XXX XX XX formatida)</i>"""

            await UserState.waiting_phone.set()
            await call.message.answer(
                success_text,
                reply_markup=phone_request_kb(),
                parse_mode="HTML"
            )
            return

        # Telefon bor - bosh menyu
        success_text = f"""✅ <b>Obuna tasdiqlandi!</b>

🎉 Endi botdan to'liq foydalanishingiz mumkin!

💳 <b>Balanslaringiz:</b>
🎁 Bepul: <b>{free_trials}</b> ta
💰 Pullik: <b>{total_balance}</b> ta

⬇️ <b>Quyidagi tugmalardan birini tanlang:</b>"""

        await call.message.answer(
            success_text,
            reply_markup=main_menu(user.id in ADMINS),
            parse_mode="HTML"
        )

    else:
        # ❌ HALI OBUNA EMAS
        await call.answer(
            "❌ Siz hali obuna bo'lmagansiz!\n\n"
            "📢 Kanalga obuna bo'lib, qaytadan tugmani bosing.",
            show_alert=True
        )


# ================ PHONE HANDLER ================
@dp.message_handler(content_types=['contact'], state=UserState.waiting_phone)
async def receive_phone(message: types.Message, state: FSMContext):
    """Telefon qabul qilish"""
    if message.contact.user_id != message.from_user.id:
        await message.answer("❌ O'Z telefon raqamingizni yuboring!", reply_markup=phone_request_kb())
        return

    phone = message.contact.phone_number
    if not phone.startswith('+'):
        phone = '+' + phone

    try:
        api_task = api.update_phone(message.from_user.id, phone)
        local_task = asyncio.to_thread(
            lambda: __import__('utils.db_api.user_database', fromlist=['update_phone_number']).update_phone_number(
                message.from_user.id, phone)
        )

        api_result, _ = await asyncio.gather(api_task, local_task, return_exceptions=True)

        if isinstance(api_result, Exception) or not api_result.get('success'):
            await message.answer("❌ Xatolik. Qaytadan /start")
            await state.finish()
            return

    except Exception as e:
        logger.error(f"Phone update error: {e}")
        await message.answer("❌ Xatolik. Qaytadan /start")
        await state.finish()
        return

    try:
        balance_result = await api.get_balance(message.from_user.id)
        balance = balance_result.get('balance', 0)
    except:
        balance = 0

    try:
        local_data = get_user_balance(message.from_user.id)
        free_trials = local_data.get('free_trials_left', FREE_TRIALS_DEFAULT)
    except:
        free_trials = FREE_TRIALS_DEFAULT

    try:
        models = get_models()
        models_text = f"✅ <b>{len(models)}</b> ta model\n"
    except:
        models_text = ""

    text = f"""✅ <b>Telefon qabul qilindi!</b>

📞 {phone}

🎁 <b>Bepul:</b> {free_trials} ta
💰 <b>Balans:</b> {balance} ta
{models_text}
<b>⬇️ Menyudan tanlang:</b>"""

    await state.finish()
    await message.answer(text, reply_markup=main_menu(message.from_user.id in ADMINS), parse_mode="HTML")


@dp.message_handler(state=UserState.waiting_phone)
async def phone_state_handler(message: types.Message, state: FSMContext):
    """Phone state"""
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        await state.finish()
        await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        return
    await message.answer("📱 Iltimos, tugmani bosing!", reply_markup=phone_request_kb())


# ================ ADMIN PANEL ================
# ================ ADMIN PANEL ================
@dp.message_handler(lambda m: m.text == "🔧 Admin panel" and m.from_user.id in ADMINS, state='*')
async def admin_panel_handler(message: types.Message, state: FSMContext):
    """Admin panel"""
    await state.finish()
    from utils.db_api.database import get_total_prices_count

    models_count = len(get_models())
    prices_count = get_total_prices_count()
    tariffs_result = await api.get_tariffs()
    tariffs_count = len(tariffs_result.get('tariffs', [])) if tariffs_result.get('success') else 0

    # ⭐ TAMIRLASH REJIMI HOLATI
    maintenance_status = get_maintenance_status()

    text = f"""<b>👨‍💼 ADMIN PANEL</b>

📊 <b>Statistika:</b>
- 📱 Modellar: {models_count} ta
- 💰 Narxlar: {prices_count} ta
- 💳 Tariflar: {tariffs_count} ta
- 👥 Adminlar: {len(ADMINS)} ta

🔧 <b>Tamirlash rejimi:</b> {maintenance_status}

<b>🔧 Amallar:</b>
Statistika, Tariflar, Excel import/export, Tozalash, Namuna
"""
    await message.answer(text, reply_markup=admin_kb(), parse_mode="HTML")


# ================ MY ACCOUNT ================
@dp.message_handler(lambda m: m.text == "👤 Mening hisobim", state='*')
async def my_account(message: types.Message, state: FSMContext):
    """Mening hisobim"""
    await state.finish()

    # ⚠️ TAMIRLASH TEKSHIRISH
    if not is_feature_enabled('account'):
        maintenance_text = f"""🔧 <b>TEXNIK ISHLAR</b>

⚠️ <b>Hurmatli foydalanuvchi!</b>

Bot hozirda texnik ishlar olib borilmoqda.
Hisob ma'lumotlari vaqtincha ko'rsatilmaydi.

⏰ <b>Ishga tushish vaqti:</b> Tez orada e'lon qilinadi

📢 <b>Yangiliklar uchun:</b>
{TELEGRAM_CHANNEL}

Tushunganingiz uchun rahmat!"""

        await message.answer(
            maintenance_text,
            reply_markup=main_menu(message.from_user.id in ADMINS),
            parse_mode="HTML"
        )
        return

    # ✅ ODDIY HISOB KO'RSATISH
    result = get_user_balance(message.from_user.id)

    if not result.get('success'):
        await message.answer("❌ Xatolik")
        return

    balance = result.get('balance', 0)
    free_trials = result.get('free_trials_left', 0)
    full_name = result.get('full_name', message.from_user.full_name)
    phone = result.get('phone_number', 'Kiritilmagan')
    total = result.get('total_pricings', 0)

    text = f"""👤 <b>Shaxsiy kabinet</b>

📝 <b>Ism:</b> {full_name}
📱 <b>Telefon:</b> {phone}
🆔 <b>ID:</b> <code>{message.from_user.id}</code>
💰 <b>Balans:</b> {balance} ta
🎁 <b>Bepul:</b> {free_trials} ta
📊 <b>Jami:</b> {total} ta
"""

    if balance > 0:
        text += f"\n✅ {balance} marta narxlashingiz mumkin."
    elif free_trials > 0:
        text += f"\n🎁 {free_trials} ta bepul urinish!"
    else:
        text += "\n⚠️ Balans yetarli emas!\n💳 Hisobni to'ldiring."

    # So'nggi to'lovlar
    pay_result = get_user_payment_history(message.from_user.id, limit=3)
    payments = pay_result.get('payments', [])
    if payments:
        text += "\n\n💳 <b>So'nggi to'lovlar:</b>\n"
        for p in payments:
            status_icon = "✅" if p['payment_status'] == 'completed' else "⏳"
            date = str(p['created_at'])[:10]
            text += f"{status_icon} {p['tariff_name']} — {int(p['amount']):,} so'm ({date})\n"

    await message.answer(text, reply_markup=balance_menu_kb(), parse_mode="HTML")


# ================ BACK TO MENU ================
@dp.message_handler(lambda m: m.text in ["◀️ Orqaga", "🏠 Bosh menyu"], state="*")
async def back_to_menu(message: types.Message, state: FSMContext):
    """Bosh menyu"""
    await state.finish()
    await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))


# ================ PAYMENT HANDLERS ================
@dp.message_handler(lambda m: m.text == "💰 Hisobni to'ldirish", state='*')
async def start_payment(message: types.Message, state: FSMContext):
    """To'ldirish"""
    await state.finish()

    # ⚠️ TAMIRLASH TEKSHIRISH
    if not is_feature_enabled('payment'):
        maintenance_text = f"""🔧 <b>TEXNIK ISHLAR</b>

⚠️ <b>Hurmatli foydalanuvchi!</b>

Bot hozirda texnik ishlar olib borilmoqda.
To'lov funksiyasi vaqtincha ishlamaydi.

⏰ <b>Ishga tushish vaqti:</b> Tez orada e'lon qilinadi

📢 <b>Yangiliklar uchun:</b>
{TELEGRAM_CHANNEL}

🙏 Tushunganingiz uchun rahmat!"""

        await message.answer(
            maintenance_text,
            reply_markup=main_menu(message.from_user.id in ADMINS),
            parse_mode="HTML"
        )
        return

    # ✅ ODDIY TO'LOV JARAYONI
    result = await api.get_tariffs()

    if not result.get('success'):
        await message.answer("❌ Tariflar yuklanmadi")
        return

    tariffs = result.get('tariffs', [])
    if not tariffs:
        await message.answer("📋 Tariflar mavjud emas")
        return

    markup = create_tariffs_inline_keyboard(tariffs)
    text = "💰 <b>Hisobni to'ldirish</b>\n\nTarifni tanlang:\n\n"

    for t in tariffs:
        ppo = t['price'] / t['count']
        emoji = '1️⃣' if t['count'] == 1 else '5️⃣' if t['count'] == 5 else '🔟'
        text += f"{emoji} <b>{t['name']}</b>\n   {t['price']:,.0f} so'm ({ppo:,.0f} so'm/ta)\n\n"

    text += "👇 Tarifni tanlang:"

    await PaymentState.waiting_tariff.set()
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@dp.callback_query_handler(lambda c: c.data.startswith("tariff_"), state=PaymentState.waiting_tariff)
async def process_tariff(callback: types.CallbackQuery, state: FSMContext):
    """Tarif tanlandi"""
    await callback.answer()

    try:
        tariff_id = int(callback.data.split("_")[1])
    except:
        await callback.answer("❌ Xato", show_alert=True)
        return

    result = await api.create_payment(callback.from_user.id, tariff_id)

    if not result.get('success'):
        await callback.answer(f"❌ {result.get('error', 'Xato')}", show_alert=True)
        return

    order_id = result.get('order_id', '')
    if not order_id:
        await callback.answer("❌ Order ID yo'q", show_alert=True)
        return

    await state.update_data(
        order_id=order_id,
        payment_url=result.get('payment_url'),
        amount=result.get('amount'),
        count=result.get('count'),
        tariff_name=result.get('tariff_name')
    )

    text = f"""💳 <b>To'lov</b>

🆔 <code>{order_id}</code>
💰 {result.get('amount', 0):,.0f} so'm
📦 {result.get('count', 0)} ta

<b>To'lov qilish:</b>
1️⃣ Payme ga o'ting
2️⃣ To'lovni amalga oshiring
3️⃣ "✅ To'lov qildim" bosing

⏳ 30 daqiqa ichida!
"""

    markup = create_payment_inline_keyboard(result.get('payment_url', ''))

    try:
        await callback.message.delete()
    except:
        pass

    await PaymentState.waiting_check.set()
    await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")
    asyncio.create_task(auto_check_payment(order_id, callback.from_user.id, state))


@dp.callback_query_handler(lambda c: c.data == "check_payment", state=PaymentState.waiting_check)
async def check_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    """To'lovni tekshirish"""
    await callback.answer("🔄 Tekshirilmoqda...")

    data = await state.get_data()
    order_id = data.get('order_id')

    if not order_id:
        await callback.answer("❌ Order ID topilmadi", show_alert=True)
        return

    result = await api.check_payment_status(order_id)

    if not result.get('success') or not result.get('has_payment'):
        await callback.answer("❌ To'lov topilmadi", show_alert=True)
        return

    if result.get('state') == 2:
        text = f"""✅ <b>TO'LOV MUVAFFAQIYATLI!</b>

💰 {result.get('balance', 0)} ta
📦 {result.get('count', 0)} ta
💵 {result.get('amount', 0):,.0f} so'm

🎉 Endi narxlashingiz mumkin!
"""
        try:
            await callback.message.edit_text(text, parse_mode="HTML")
        except:
            await callback.message.answer(text, parse_mode="HTML")
        await state.finish()

    elif result.get('state') == 1:
        await callback.answer("⏳ To'lov hali qilinmadi", show_alert=True)
    else:
        await callback.answer("❌ To'lov bekor qilindi", show_alert=True)
        await state.finish()


@dp.callback_query_handler(lambda c: c.data == "cancel_payment", state=PaymentState.waiting_check)
async def cancel_payment_callback(callback: types.CallbackQuery, state: FSMContext):
    """Bekor qilish"""
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer("❌ Bekor qilindi")
    await state.finish()
    await callback.message.answer("🏠 Bosh menyu", reply_markup=main_menu(callback.from_user.id in ADMINS))


# ================ PRICING HANDLERS (⭐ MAJBURIY OBUNA BILAN) ================
@dp.message_handler(lambda m: m.text in ["📱 Telefon narxlash", "🔄 Yana hisoblash"], state='*')
async def choose_model(message: types.Message, state: FSMContext):
    """Model tanlash - MAJBURIY OBUNA BILAN"""
    await state.finish()
    user_id = message.from_user.id

    # ⚠️ TAMIRLASH TEKSHIRISH
    if not is_feature_enabled('pricing'):
        maintenance_text = f"""🔧 <b>TEXNIK ISHLAR</b>

⚠️ <b>Hurmatli foydalanuvchi!</b>

Bot hozirda texnik ishlar olib borilmoqda.
Narxlash funksiyasi vaqtincha ishlamaydi.

⏰ <b>Ishga tushish vaqti:</b> Tez orada e'lon qilinadi

📢 <b>Yangiliklar uchun:</b>
{TELEGRAM_CHANNEL}

🙏 Tushunganingiz uchun rahmat!"""

        await message.answer(
            maintenance_text,
            reply_markup=main_menu(message.from_user.id in ADMINS),
            parse_mode="HTML"
        )
        return

    # ⭐ OBUNA TEKSHIRISH (Adminlar uchun yo'q)
    if user_id not in ADMINS:
        is_subscribed = await check_subscription(user_id)

        if not is_subscribed:
            text = SUBSCRIPTION_TEXT.format(channel=CHANNEL_USERNAME)
            await message.answer(text, reply_markup=subscription_keyboard(), parse_mode="HTML")
            return

    # ============================================================
    # ⭐ USER MAVJUDLIGINI TEKSHIRISH
    # ============================================================
    local_check = check_can_price(user_id)

    # Agar user bazada yo'q bo'lsa - /start bosishni talab qilish
    if local_check.get('reason') == 'User topilmadi':
        text = """❌ <b>Siz hali ro'yxatdan o'tmagansiz!</b>

📝 Iltimos, botni ishga tushirish uchun /start bosing.

🎁 Ro'yxatdan o'tganingizda <b>{FREE_TRIALS_DEFAULT} ta bepul urinish</b> olasiz!"""

        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("/start"))

        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    # ============================================================
    # ⭐ BALANS TEKSHIRISH
    # ============================================================
    if local_check.get("need_phone"):
        await message.answer(local_check.get("message", "📱 Telefon kerak"))
        return

    free_trials = int(local_check.get("free_trials_left", 0) or 0)

    api_balance = 0
    if free_trials <= 0:
        try:
            api_res = await api.get_balance(user_id)
            api_balance = int(api_res.get("balance", 0) or 0)
        except:
            api_balance = 0

    if free_trials <= 0 and api_balance <= 0:
        text = f"""❌ <b>Balans yetarli emas!</b>

🎁 <b>Bepul:</b> 0 ta
💰 <b>Balans:</b> {api_balance} ta

💡 <b>Hisobni to'ldiring:</b>"""

        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("💰 Hisobni to'ldirish"))
        kb.row(KeyboardButton("🏠 Bosh menyu"))
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
        return

    models = get_models()
    if not models:
        await message.answer("❌ Modellar topilmadi")
        return

    sorted_models = sort_models_naturally(models)
    kb = create_keyboard([m['name'] for m in sorted_models], row_width=2)

    status = f"🎁 <b>Bepul: {free_trials} ta</b>" if free_trials > 0 else f"💰 <b>Balans: {api_balance} ta</b>"

    text = f"""📱 <b>Telefon narxlash</b>

{status}

<b>Modelni tanlang:</b>"""

    await UserState.waiting_model.set()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@dp.message_handler(state=UserState.waiting_model)
async def model_selected(message: types.Message, state: FSMContext):
    """Model tanlandi"""
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        await state.finish()
        await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    models = get_models() or []
    if not models:
        await state.finish()
        await message.answer("❌ Modellar topilmadi", reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    model_map = {m.get("name"): m for m in models if m.get("name") and m.get("id")}
    selected = model_map.get(message.text)

    if not selected:
        sorted_models = sort_models_naturally(models)
        kb = create_keyboard([m['name'] for m in sorted_models], row_width=2)
        await message.answer("❌ Model topilmadi:", reply_markup=kb)
        return

    await state.update_data(model_id=selected["id"], model_name=selected["name"])

    storages = get_storages(selected["id"]) or []

    if not storages:
        sorted_models = sort_models_naturally(models)
        kb = create_keyboard([m['name'] for m in sorted_models], row_width=2)
        await message.answer("❌ Xotira topilmadi. Boshqa model:", reply_markup=kb)
        await UserState.waiting_model.set()
        return

    sorted_storages = sort_storages_naturally(storages)
    kb = create_keyboard([s['size'] for s in sorted_storages], row_width=2)
    await message.answer("<b>💾 Xotira:</b>", reply_markup=kb, parse_mode="HTML")
    await UserState.waiting_storage.set()


@dp.message_handler(state=UserState.waiting_storage)
async def storage_selected(message: types.Message, state: FSMContext):
    """Xotira tanlandi"""
    data = await state.get_data()

    if 'model_id' not in data:
        await state.finish()
        await message.answer("❌ Jarayon buzildi. 📱 Telefon narxlash",
                             reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        if message.text == "🏠 Bosh menyu":
            await state.finish()
            await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        else:
            models = get_models()
            sorted_models = sort_models_naturally(models)
            kb = create_keyboard([m['name'] for m in sorted_models], row_width=2)
            await message.answer("<b>📱 Model:</b>", reply_markup=kb, parse_mode="HTML")
            await UserState.waiting_model.set()
        return

    await state.update_data(storage=message.text)
    data = await state.get_data()

    colors = get_colors(data['model_id']) or []

    if colors:
        kb = create_keyboard([c['name'] for c in colors], row_width=2)
        await message.answer("<b>🎨 Rang:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_color.set()
    else:
        await state.update_data(color="Standart")
        batteries = get_batteries(data['model_id']) or [{"label": "100%"}]
        sorted_batteries = sort_batteries_naturally(batteries)
        kb = create_keyboard([b['label'] for b in sorted_batteries], row_width=2)
        await message.answer("<b>🔋 Batareya:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_battery.set()


@dp.message_handler(state=UserState.waiting_color)
async def color_selected(message: types.Message, state: FSMContext):
    """Rang tanlandi"""
    data = await state.get_data()

    if 'model_id' not in data:
        await state.finish()
        await message.answer("❌ Jarayon buzildi. 📱 Telefon narxlash",
                             reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        if message.text == "🏠 Bosh menyu":
            await state.finish()
            await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        else:
            storages = get_storages(data['model_id']) or []
            sorted_storages = sort_storages_naturally(storages)
            kb = create_keyboard([s['size'] for s in sorted_storages], row_width=2)
            await message.answer("<b>💾 Xotira:</b>", reply_markup=kb, parse_mode="HTML")
            await UserState.waiting_storage.set()
        return

    await state.update_data(color=message.text)
    data = await state.get_data()

    batteries = get_batteries(data['model_id']) or [{"label": "100%"}]
    sorted_batteries = sort_batteries_naturally(batteries)
    kb = create_keyboard([b['label'] for b in sorted_batteries], row_width=2)
    await message.answer("<b>🔋 Batareya:</b>", reply_markup=kb, parse_mode="HTML")
    await UserState.waiting_battery.set()


@dp.message_handler(state=UserState.waiting_battery)
async def battery_selected(message: types.Message, state: FSMContext):
    """Batareya tanlandi"""
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        if message.text == "🏠 Bosh menyu":
            await state.finish()
            await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        else:
            data = await state.get_data()
            colors = get_colors(data['model_id'])
            if colors:
                kb = create_keyboard([c['name'] for c in colors], row_width=2)
                await message.answer("<b>🎨 Rang:</b>", reply_markup=kb, parse_mode="HTML")
                await UserState.waiting_color.set()
            else:
                storages = get_storages(data['model_id'])
                sorted_storages = sort_storages_naturally(storages)
                kb = create_keyboard([s['size'] for s in sorted_storages], row_width=2)
                await message.answer("<b>💾 Xotira:</b>", reply_markup=kb, parse_mode="HTML")
                await UserState.waiting_storage.set()
        return

    await state.update_data(battery=message.text)
    data = await state.get_data()
    model_name = data.get('model_name', '')

    if should_ask_sim_type(model_name):
        await state.update_data(sim_step_shown=True)
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("📱 SIM karta"), KeyboardButton("📲 eSIM"))
        kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
        await message.answer("<b>📞 SIM:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_sim.set()
    else:
        await state.update_data(sim_step_shown=False)
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("✅ Bor"), KeyboardButton("❌ Yo'q"))
        kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
        await message.answer("<b>📦 Quti:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_box.set()
        await state.update_data(sim_type="physical")


@dp.message_handler(state=UserState.waiting_sim)
async def sim_selected(message: types.Message, state: FSMContext):
    """SIM tanlandi"""
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        if message.text == "🏠 Bosh menyu":
            await state.finish()
            await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        else:
            data = await state.get_data()
            batteries = get_batteries(data['model_id']) or [{"label": "100%"}]
            sorted_batteries = sort_batteries_naturally(batteries)
            kb = create_keyboard([b['label'] for b in sorted_batteries], row_width=2)
            await message.answer("<b>🔋 Batareya:</b>", reply_markup=kb, parse_mode="HTML")
            await UserState.waiting_battery.set()
        return

    sim_type = "esim" if "eSIM" in message.text else "physical"
    await state.update_data(sim_type=sim_type)

    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Bor"), KeyboardButton("❌ Yo'q"))
    kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
    await message.answer("<b>📦 Quti:</b>", reply_markup=kb, parse_mode="HTML")
    await UserState.waiting_box.set()


@dp.message_handler(state=UserState.waiting_box)
async def box_selected(message: types.Message, state: FSMContext):
    """Quti tanlandi"""
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        if message.text == "🏠 Bosh menyu":
            await state.finish()
            await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
            return

        data = await state.get_data()
        model_name = data.get('model_name', '')

        if data.get('sim_step_shown'):
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row(KeyboardButton("📱 SIM karta"), KeyboardButton("📲 eSIM"))
            kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
            await message.answer("<b>📞 SIM:</b>", reply_markup=kb, parse_mode="HTML")
            await UserState.waiting_sim.set()
            return

        if 'model_id' not in data:
            await state.finish()
            await message.answer("❌ Jarayon buzildi. 📱 Telefon narxlash",
                                 reply_markup=main_menu(message.from_user.id in ADMINS))
            return

        batteries = get_batteries(data['model_id']) or [{"label": "100%"}]
        sorted_batteries = sort_batteries_naturally(batteries)
        kb = create_keyboard([b['label'] for b in sorted_batteries], row_width=2)
        await message.answer("<b>🔋 Batareya:</b>", reply_markup=kb, parse_mode="HTML")
        await UserState.waiting_battery.set()
        return

    if message.text not in ["✅ Bor", "❌ Yo'q"]:
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("✅ Bor"), KeyboardButton("❌ Yo'q"))
        kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
        await message.answer("❌ Tugmalardan tanlang:", reply_markup=kb)
        return

    has_box = "Bor" if message.text == "✅ Bor" else "Yo'q"
    await state.update_data(has_box=has_box)

    await message.answer(
        "<b>🔧 Telefonning qismlari almashganmi?</b>",
        reply_markup=parts_choice_kb(),
        parse_mode="HTML"
    )
    await UserState.waiting_parts_choice.set()


# ================ QISMLAR TANLOVI ================
@dp.message_handler(state=UserState.waiting_parts_choice)
async def parts_choice_selected(message: types.Message, state: FSMContext):
    """Qismlar tanlovi"""
    if message.text in ["◀️ Orqaga", "🏠 Bosh menyu"]:
        if message.text == "🏠 Bosh menyu":
            await state.finish()
            await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        else:
            from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row(KeyboardButton("✅ Bor"), KeyboardButton("❌ Yo'q"))
            kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))
            await message.answer("<b>📦 Quti:</b>", reply_markup=kb, parse_mode="HTML")
            await UserState.waiting_box.set()
        return

    if message.text == "❌ Yo'q":
        await state.update_data(selected_parts=[], damage_display="Yangi")
        await show_final_price(message, state)
        return

    if message.text == "✅ Ha":
        await state.update_data(selected_parts=[])
        markup = create_parts_inline_kb([], PARTS)

        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("◀️ Orqaga"), KeyboardButton("🏠 Bosh menyu"))

        await message.answer(
            "<b>🔧 Almashgan qismlar (maks 3 ta):</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await message.answer("⬇️ Qismlardan tanlang:", reply_markup=markup)
        await UserState.waiting_parts.set()
        return

    await message.answer("❌ Tugmalardan birini tanlang:", reply_markup=parts_choice_kb())


# ================ QISMLAR - INLINE ================
@dp.callback_query_handler(state=UserState.waiting_parts)
async def parts_callback(call: types.CallbackQuery, state: FSMContext):
    """Qismlar"""
    data = await state.get_data()
    selected = data.get('selected_parts', [])

    if call.data == "part_done":
        if not selected:
            await call.answer("❌ Hech narsa tanlanmadi!", show_alert=True)
            return

        damage_display = " + ".join([PARTS[k] for k in sorted(selected)])
        await state.update_data(damage_display=damage_display)

        try:
            await call.message.delete()
        except:
            pass

        await show_final_price_from_callback(call, state)
        await call.answer()
        return

    part_key = call.data.replace("part_", "")

    if part_key in ("screen", "glass"):
        other = "glass" if part_key == "screen" else "screen"
        if other in selected:
            await call.answer("❌ Ekran va Oyna birga bo'lmaydi!", show_alert=True)
            return

    if part_key in selected:
        selected.remove(part_key)
    else:
        if len(selected) >= 3:
            await call.answer("❌ Maks 3 ta!", show_alert=True)
            return
        selected.append(part_key)

    await state.update_data(selected_parts=selected)
    markup = create_parts_inline_kb(selected, PARTS)

    text = f"<b>🔧 Tanlangan:</b> {', '.join([PARTS[k] for k in sorted(selected)])}" if selected else "<b>🔧 Qismlar (maks 3):</b>"

    try:
        await call.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except MessageNotModified:
        pass

    await call.answer()


# ================ WAITING_PARTS - BACK BUTTON ================
@dp.message_handler(lambda m: m.text in ["◀️ Orqaga", "🏠 Bosh menyu"], state=UserState.waiting_parts)
async def waiting_parts_back(message: types.Message, state: FSMContext):
    """waiting_parts dan orqaga - qismlar tanlovi sahifasiga"""
    if message.text == "🏠 Bosh menyu":
        await state.finish()
        await message.answer("🏠 Bosh menyu", reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    # Orqaga → waiting_parts_choice ga qaytish
    await message.answer(
        "<b>🔧 Telefonning qismlari almashganmi?</b>",
        reply_markup=parts_choice_kb(),
        parse_mode="HTML"
    )
    await UserState.waiting_parts_choice.set()


# ================ FINAL PRICE - CALLBACK ================
async def show_final_price_from_callback(call: types.CallbackQuery, state: FSMContext):
    """Yakuniy narx - CALLBACK"""
    data = await state.get_data()

    required_fields = ['model_name', 'model_id', 'storage']
    for field in required_fields:
        if field not in data:
            await call.message.answer(
                "❌ Jarayon buzildi. Qaytadan boshlang:\n📱 Telefon narxlash",
                reply_markup=main_menu(call.from_user.id in ADMINS)
            )
            await state.finish()
            return

    selected = data.get('selected_parts', [])
    color = data.get('color', 'Standart')
    battery = data.get('battery', '100%')
    sim_type = data.get('sim_type', 'physical')
    has_box = data.get('has_box', "Yo'q")

    damage_display = "Yangi" if not selected else data.get('damage_display',
                                                           " + ".join([PARTS[k] for k in sorted(selected)]))

    safe_data = {
        'model_id': data['model_id'],
        'model_name': data['model_name'],
        'storage': data['storage'],
        'color': color,
        'battery': battery,
        'sim_type': sim_type,
        'has_box': has_box,
        'selected_parts': selected
    }

    final_price = calculate_final_price(safe_data)
    phone_model = f"{data['model_name']} {data['storage']}"

    if isinstance(final_price, str):
        price_str = final_price.replace(" $", "").replace("$", "").replace(" ", "").replace(",", "")
        try:
            price_value = int(float(price_str))
        except:
            price_value = 0
    else:
        price_value = int(final_price)

    user_id = call.from_user.id

    local_check = check_can_price(user_id)
    free_trials = int(local_check.get("free_trials_left", 0) or 0)

    is_free = False
    balance = 0

    if free_trials > 0:
        local_res = use_pricing_local(
            user_id, phone_model, data['storage'], color,
            battery, sim_type, has_box, damage_display, price_value
        )

        if not local_res.get("success"):
            await call.message.answer(f"❌ {local_res.get('error')}", reply_markup=main_menu(user_id in ADMINS))
            await state.finish()
            return

        is_free = True
        free_trials = int(local_res.get("free_trials_left", 0) or 0)

        try:
            api_res = await api.get_balance(user_id)
            balance = int(api_res.get("balance", 0) or 0)
        except:
            balance = 0

    else:
        try:
            api_res = await api.use_pricing(user_id, phone_model, price_value)
        except Exception as e:
            await call.message.answer("❌ Server bilan aloqa uzildi. Bir daqiqadan so'ng qaytadan urinib ko'ring.", reply_markup=main_menu(user_id in ADMINS))
            await state.finish()
            return

        if not api_res.get("success"):
            await call.message.answer(f"❌ {api_res.get('error')}", reply_markup=main_menu(user_id in ADMINS))
            await state.finish()
            return

        is_free = False
        balance = int(api_res.get("balance", 0) or 0)

    now = uz_now()
    display_price = final_price if isinstance(final_price, str) else f"${price_value:,.0f}".replace(",", " ")

    text = f"""📊 <b>NATIJA</b>

📱 <b>Model:</b> {data['model_name']}
💾 <b>Xotira:</b> {data['storage']}
🎨 <b>Rang:</b> {color}
📞 <b>SIM:</b> {'📲 eSIM' if sim_type == 'esim' else '📱 SIM'}
🔋 <b>Batareya:</b> {battery}
📦 <b>Quti:</b> {'✅ Bor' if has_box == 'Bor' else '❌ Yo`q'}
🔧 <b>Holat:</b> {damage_display}

💰 <b>Narx:</b> <code>{display_price}</code>

🕒 {now}
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    inline_kb = InlineKeyboardMarkup()
    inline_kb.add(InlineKeyboardButton("🔄 Qayta narxlash", callback_data="reprice"))

    await call.message.answer(text, reply_markup=inline_kb, parse_mode="HTML")
    await call.message.answer("🏠 Bosh menyu", reply_markup=main_menu(call.from_user.id in ADMINS))
    await state.finish()


# ================ FINAL PRICE - MESSAGE ================
async def show_final_price(message: types.Message, state: FSMContext):
    """Yakuniy narx - MESSAGE"""
    data = await state.get_data()

    model_name = data.get("model_name")
    storage = data.get("storage")

    if not model_name or not storage:
        await state.finish()
        await message.answer("❌ Jarayon buzildi. 📱 Telefon narxlash",
                             reply_markup=main_menu(message.from_user.id in ADMINS))
        return

    color = data.get("color") or "Standart"
    battery = data.get("battery") or "100%"
    sim_type = data.get("sim_type") or "physical"
    has_box = data.get("has_box") or "Yo'q"
    selected = data.get("selected_parts", []) or []
    damage_display = data.get("damage_display") or (
        "Yangi" if not selected else " + ".join([PARTS[k] for k in sorted(selected)]))

    safe_data = dict(data)
    safe_data.update({
        "color": color,
        "battery": battery,
        "sim_type": sim_type,
        "has_box": has_box,
        "selected_parts": selected,
        "damage_display": damage_display
    })

    final_price = calculate_final_price(safe_data)
    phone_model = f"{model_name} {storage}"

    if isinstance(final_price, str):
        price_str = final_price.replace(" $", "").replace("$", "").replace(" ", "").replace(",", "")
        try:
            price_value = int(float(price_str))
        except:
            price_value = 0
    else:
        price_value = int(final_price)

    user_id = message.from_user.id

    local_check = check_can_price(user_id)
    free_trials = int(local_check.get("free_trials_left", 0) or 0)

    is_free = False
    balance = 0

    if free_trials > 0:
        local_res = use_pricing_local(
            user_id, phone_model, storage, color, battery,
            sim_type, has_box, damage_display, price_value
        )

        if not local_res.get("success"):
            await message.answer(f"❌ {local_res.get('error')}", reply_markup=main_menu(user_id in ADMINS))
            await state.finish()
            return

        is_free = True
        free_trials = int(local_res.get("free_trials_left", 0) or 0)

        try:
            api_res = await api.get_balance(user_id)
            balance = int(api_res.get("balance", 0) or 0)
        except:
            balance = 0

    else:
        try:
            api_res = await api.use_pricing(user_id, phone_model, price_value)
        except Exception as e:
            await message.answer("❌ Server bilan aloqa uzildi. Bir daqiqadan so'ng qaytadan urinib ko'ring.", reply_markup=main_menu(user_id in ADMINS))
            await state.finish()
            return

        if not api_res.get("success"):
            await message.answer(f"❌ {api_res.get('error')}", reply_markup=main_menu(user_id in ADMINS))
            await state.finish()
            return

        is_free = False
        balance = int(api_res.get("balance", 0) or 0)

    now = uz_now()
    display_price = final_price if isinstance(final_price, str) else f"${price_value:,.0f}".replace(",", " ")

    text = f"""📊 <b>NATIJA</b>

📱 <b>Model:</b> {model_name}
💾 <b>Xotira:</b> {storage}
🎨 <b>Rang:</b> {color}
📞 <b>SIM:</b> {'📲 eSIM' if sim_type == 'esim' else '📱 SIM'}
🔋 <b>Batareya:</b> {battery}
📦 <b>Quti:</b> {'✅ Bor' if has_box == 'Bor' else '❌ Yo`q'}
🔧 <b>Holat:</b> {damage_display}

💰 <b>Narx:</b> <code>{display_price}</code>

🕒 {now}
"""

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    inline_kb = InlineKeyboardMarkup()
    inline_kb.add(InlineKeyboardButton("🔄 Qayta narxlash", callback_data="reprice"))

    await message.answer(text, reply_markup=inline_kb, parse_mode="HTML")
    await message.answer("🏠 Bosh menyu", reply_markup=main_menu(user_id in ADMINS))
    await state.finish()


# ================ REPRICE CALLBACK ================
@dp.callback_query_handler(lambda c: c.data == "reprice", state='*')
async def reprice_callback(call: types.CallbackQuery, state: FSMContext):
    """Qayta narxlash inline tugmasi"""
    await call.answer()
    await state.finish()
    user_id = call.from_user.id

    if not is_feature_enabled('pricing'):
        await call.message.answer("🔧 Narxlash hozirda texnik ishlar sababli ishlamaydi.",
                                  reply_markup=main_menu(user_id in ADMINS))
        return

    if user_id not in ADMINS:
        is_subscribed = await check_subscription(user_id)
        if not is_subscribed:
            text = SUBSCRIPTION_TEXT.format(channel=CHANNEL_USERNAME)
            await call.message.answer(text, reply_markup=subscription_keyboard(), parse_mode="HTML")
            return

    local_check = check_can_price(user_id)
    if local_check.get('reason') == 'User topilmadi':
        await call.message.answer("❌ Iltimos, /start bosing.", reply_markup=main_menu(user_id in ADMINS))
        return
    if local_check.get("need_phone"):
        await call.message.answer(local_check.get("message", "📱 Telefon kerak"))
        return

    free_trials = int(local_check.get("free_trials_left", 0) or 0)
    api_balance = 0
    if free_trials <= 0:
        try:
            api_res = await api.get_balance(user_id)
            api_balance = int(api_res.get("balance", 0) or 0)
        except:
            api_balance = 0

    if free_trials <= 0 and api_balance <= 0:
        from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("💰 Hisobni to'ldirish"))
        kb.row(KeyboardButton("🏠 Bosh menyu"))
        await call.message.answer(
            f"❌ <b>Balans yetarli emas!</b>\n\n🎁 <b>Bepul:</b> 0 ta\n💰 <b>Balans:</b> {api_balance} ta\n\n💡 <b>Hisobni to'ldiring:</b>",
            reply_markup=kb, parse_mode="HTML"
        )
        return

    models = get_models()
    if not models:
        await call.message.answer("❌ Modellar topilmadi")
        return

    sorted_models = sort_models_naturally(models)
    kb = create_keyboard([m['name'] for m in sorted_models], row_width=2)
    status = f"🎁 <b>Bepul: {free_trials} ta</b>" if free_trials > 0 else f"💰 <b>Balans: {api_balance} ta</b>"
    await UserState.waiting_model.set()
    await call.message.answer(
        f"📱 <b>Telefon narxlash</b>\n\n{status}\n\n<b>Modelni tanlang:</b>",
        reply_markup=kb, parse_mode="HTML"
    )


# ================ ABOUT ================
@dp.message_handler(lambda m: m.text == "ℹ️ Biz haqimizda", state='*')
async def about_handler(message: types.Message, state: FSMContext):
    """Biz haqimizda"""
    await state.finish()
    await message.answer(ABOUT_TEXT, parse_mode="HTML")