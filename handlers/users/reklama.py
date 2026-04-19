# handlers/users/reklama.py
import asyncio
import datetime
import logging

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import (
    BotBlocked, ChatNotFound, RetryAfter,
    Unauthorized, UserDeactivated, MessageNotModified,
    CantTalkWithBots
)

from data.config import ADMINS
from loader import bot, dp
from utils.db_api.user_database import get_all_users, get_all_users_count

logger = logging.getLogger(__name__)

# Faol reklamalar ro'yxati
advertisements: list = []


# ────────────────────────────────────────────
# States
# ────────────────────────────────────────────
class ReklamaTuriState(StatesGroup):
    tur        = State()
    vaqt       = State()
    time_value = State()
    content    = State()
    buttons    = State()


# ────────────────────────────────────────────
# Advertisement klassi
# ────────────────────────────────────────────
class Advertisement:
    def __init__(self, ad_id, message, ad_type,
                 keyboard=None, send_time=None, creator_id=None):
        self.ad_id        = ad_id
        self.message      = message
        self.ad_type      = ad_type
        self.keyboard     = keyboard
        self.send_time    = send_time
        self.creator_id   = creator_id

        self.running      = False
        self.paused       = False
        self.sent_count   = 0
        self.failed_count = 0
        self.total_users  = 0
        self.start_time   = None
        self.status_msg   = None
        self.task         = None

    # ── progress bar ──────────────────────────
    def _progress_bar(self) -> str:
        done    = self.sent_count + self.failed_count
        pct     = int(done / self.total_users * 20) if self.total_users else 0
        bar     = "█" * pct + "░" * (20 - pct)
        percent = int(done / self.total_users * 100) if self.total_users else 0
        return f"[{bar}] {percent}%"

    def _elapsed(self) -> str:
        if not self.start_time:
            return "—"
        secs = int((datetime.datetime.now() - self.start_time).total_seconds())
        m, s = divmod(secs, 60)
        return f"{m}:{s:02d}"

    def _build_text(self, status: str) -> str:
        done = self.sent_count + self.failed_count
        return (
            f"📣 <b>Reklama #{self.ad_id}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{self._progress_bar()}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ Yuborildi:    <b>{self.sent_count}</b>\n"
            f"❌ Yuborilmadi: <b>{self.failed_count}</b>\n"
            f"👥 Jami:        <b>{done}/{self.total_users}</b>\n"
            f"⏱ Vaqt:         <b>{self._elapsed()}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🔹 Holat: <b>{status}</b>"
        )

    async def _update_status(self, status: str, finished=False):
        if not self.status_msg:
            return
        markup = None if finished else get_status_keyboard(self.ad_id, self.paused)
        try:
            await self.status_msg.edit_text(
                self._build_text(status),
                parse_mode="HTML",
                reply_markup=markup
            )
        except MessageNotModified:
            pass
        except Exception as e:
            logger.warning(f"Status xabarini yangilashda xatolik: {e}")

    # ── asosiy yuborish sikli ─────────────────
    async def start(self):
        self.running    = True
        self.start_time = datetime.datetime.now()

        if self.send_time:
            delay = (self.send_time - datetime.datetime.now()).total_seconds()
            if delay > 0:
                await asyncio.sleep(delay)

        users            = get_all_users()
        self.total_users = len(users)

        try:
            self.status_msg = await bot.send_message(
                chat_id=self.creator_id,
                text=self._build_text("Boshlandi ⚡"),
                parse_mode="HTML",
                reply_markup=get_status_keyboard(self.ad_id)
            )
        except Exception as e:
            logger.error(f"Status xabar yuborishda xatolik: {e}")

        UPDATE_EVERY = 10
        DELAY        = 0.05
        CHUNK_SIZE   = 300
        CHUNK_PAUSE  = 300

        for i, user in enumerate(users):
            if not self.running:
                break

            while self.paused:
                await asyncio.sleep(1)
                if not self.running:
                    break
            if not self.running:
                break

            await self._send_with_retry(user['telegram_id'])
            await asyncio.sleep(DELAY)

            if (i + 1) % UPDATE_EVERY == 0:
                await self._update_status("Davom etmoqda ▶️")

            if (i + 1) % CHUNK_SIZE == 0 and (i + 1) < self.total_users:
                for remaining in range(CHUNK_PAUSE, 0, -1):
                    if not self.running:
                        break
                    await self._update_status(f"⏳ Telegram limit: {remaining}s dam olmoqda...")
                    await asyncio.sleep(1)

        self.running = False
        self.paused  = False
        await self._update_status("✅ Yakunlandi", finished=True)

    async def _send_with_retry(self, chat_id: int, max_retries: int = 3):
        for attempt in range(max_retries):
            if not self.running:
                return
            try:
                await asyncio.wait_for(_send_to_user(chat_id, self), timeout=20)
                self.sent_count += 1
                return
            except asyncio.TimeoutError:
                logger.warning(f"User {chat_id} ga yuborishda timeout (urinish {attempt + 1})")
                self.failed_count += 1
                return
            except RetryAfter as e:
                wait = e.timeout + 1
                logger.info(f"FloodWait {wait}s, kutilmoqda...")
                await self._update_status(f"⏳ FloodWait {wait}s kutilmoqda...")
                for _ in range(wait):
                    if not self.running:
                        return
                    await asyncio.sleep(1)
            except (BotBlocked, ChatNotFound, Unauthorized,
                    UserDeactivated, CantTalkWithBots):
                self.failed_count += 1
                return
            except Exception as e:
                logger.warning(f"User {chat_id} ga yuborishda xatolik (urinish {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5)
        self.failed_count += 1

    async def pause(self):
        self.paused = True
        await self._update_status("⏸ Pauza")

    async def resume(self):
        self.paused = False
        await self._update_status("Davom etmoqda ▶️")

    async def stop(self):
        self.running = False
        await self._update_status("⛔ To'xtatildi", finished=True)


# ────────────────────────────────────────────
# Yuborish yordamchi funksiyalari
# ────────────────────────────────────────────
async def _send_to_user(chat_id: int, ad: Advertisement):
    msg      = ad.message
    ad_type  = ad.ad_type
    keyboard = ad.keyboard
    caption  = msg.caption or msg.text or ""

    if ad_type == "ad_type_text":
        await bot.send_message(chat_id=chat_id, text=caption)

    elif ad_type == "ad_type_forward":
        await bot.forward_message(
            chat_id=chat_id,
            from_chat_id=msg.chat.id,
            message_id=msg.message_id
        )

    elif ad_type == "ad_type_button":
        await _send_with_keyboard(chat_id, msg, keyboard, caption)

    else:  # ad_type_any
        await _send_any(chat_id, msg)


async def _send_with_keyboard(chat_id, msg, keyboard, caption):
    ct = msg.content_type
    if ct == types.ContentType.TEXT:
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)
    elif ct == types.ContentType.PHOTO:
        await bot.send_photo(chat_id=chat_id, photo=msg.photo[-1].file_id,
                             caption=caption, reply_markup=keyboard)
    elif ct == types.ContentType.VIDEO:
        await bot.send_video(chat_id=chat_id, video=msg.video.file_id,
                             caption=caption, reply_markup=keyboard)
    elif ct == types.ContentType.DOCUMENT:
        await bot.send_document(chat_id=chat_id, document=msg.document.file_id,
                                caption=caption, reply_markup=keyboard)
    elif ct == types.ContentType.AUDIO:
        await bot.send_audio(chat_id=chat_id, audio=msg.audio.file_id,
                             caption=caption, reply_markup=keyboard)
    elif ct == types.ContentType.ANIMATION:
        await bot.send_animation(chat_id=chat_id, animation=msg.animation.file_id,
                                 caption=caption, reply_markup=keyboard)
    else:
        await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)


async def _send_any(chat_id, msg):
    ct = msg.content_type
    if ct == types.ContentType.TEXT:
        await bot.send_message(chat_id=chat_id, text=msg.text or "")
    elif ct == types.ContentType.PHOTO:
        await bot.send_photo(chat_id=chat_id, photo=msg.photo[-1].file_id,
                             caption=msg.caption)
    elif ct == types.ContentType.VIDEO:
        await bot.send_video(chat_id=chat_id, video=msg.video.file_id,
                             caption=msg.caption)
    elif ct == types.ContentType.DOCUMENT:
        await bot.send_document(chat_id=chat_id, document=msg.document.file_id,
                                caption=msg.caption)
    elif ct == types.ContentType.AUDIO:
        await bot.send_audio(chat_id=chat_id, audio=msg.audio.file_id,
                             caption=msg.caption)
    elif ct == types.ContentType.ANIMATION:
        await bot.send_animation(chat_id=chat_id, animation=msg.animation.file_id,
                                 caption=msg.caption)
    elif ct == types.ContentType.VOICE:
        await bot.send_voice(chat_id=chat_id, voice=msg.voice.file_id,
                             caption=msg.caption)
    elif ct == types.ContentType.VIDEO_NOTE:
        await bot.send_video_note(chat_id=chat_id, video_note=msg.video_note.file_id)
    else:
        await bot.send_message(chat_id=chat_id, text="Kontent turi qo'llab-quvvatlanmaydi.")


# ────────────────────────────────────────────
# Handlers
# ────────────────────────────────────────────
@dp.message_handler(lambda m: m.text == "📢 Reklama" and m.from_user.id in ADMINS)
async def reklama_handler(message: types.Message):
    await ReklamaTuriState.tur.set()
    await message.answer("📣 Reklama turini tanlang:", reply_markup=get_ad_type_keyboard())


@dp.callback_query_handler(
    lambda c: c.data in ["ad_type_text", "ad_type_forward", "ad_type_button", "ad_type_any"],
    state=ReklamaTuriState.tur
)
async def handle_ad_type(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(ad_type=cb.data)
    await ReklamaTuriState.vaqt.set()
    await cb.message.edit_text("🕐 Yuborish vaqtini tanlang:", reply_markup=get_time_keyboard())
    await cb.answer()


@dp.callback_query_handler(
    lambda c: c.data in ["send_now", "send_later"],
    state=ReklamaTuriState.vaqt
)
async def handle_send_time(cb: types.CallbackQuery, state: FSMContext):
    await state.update_data(send_time=cb.data)
    if cb.data == "send_later":
        await ReklamaTuriState.time_value.set()
        await cb.message.edit_text(
            "🕐 Yuborish vaqtini kiriting (HH:MM formatida):\nMasalan: <b>14:30</b>",
            parse_mode="HTML"
        )
    else:
        await ReklamaTuriState.content.set()
        await cb.message.edit_text(
            "📩 Reklama kontentini yuboring:",
            reply_markup=get_cancel_keyboard()
        )
    await cb.answer()


@dp.message_handler(state=ReklamaTuriState.time_value)
async def handle_time_input(message: types.Message, state: FSMContext):
    try:
        send_time = datetime.datetime.strptime(message.text.strip(), "%H:%M")
        now       = datetime.datetime.now()
        send_time = send_time.replace(year=now.year, month=now.month, day=now.day)
        if send_time < now:
            send_time += datetime.timedelta(days=1)
        await state.update_data(send_time_value=send_time)
        await ReklamaTuriState.content.set()
        await message.reply(
            f"✅ Reklama <b>{send_time.strftime('%H:%M')}</b> da yuboriladi.\n\n"
            f"📩 Reklama kontentini yuboring:",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
    except ValueError:
        await message.reply(
            "❌ Noto'g'ri format. HH:MM ko'rinishida kiriting. Masalan: <b>14:30</b>",
            parse_mode="HTML"
        )


@dp.message_handler(state=ReklamaTuriState.content, content_types=types.ContentType.ANY)
async def rek_state(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMINS:
        await message.reply("🚫 Sizda ruxsat yo'q.")
        return
    data    = await state.get_data()
    ad_type = data.get("ad_type")
    await state.update_data(ad_content=message)

    if ad_type == "ad_type_button":
        await ReklamaTuriState.buttons.set()
        await message.reply(
            "🔘 Tugmalarni quyidagi formatda kiriting:\n"
            "<code>Tugma nomi - https://url.com</code>\n"
            "Bir nechta: vergul bilan ajrating\n"
            "<code>Tugma1 - https://url1.com, Tugma2 - https://url2.com</code>",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
    else:
        total = get_all_users_count()
        await message.reply(
            f"👥 Jami <b>{total}</b> ta foydalanuvchiga yuboriladi.\n\nTasdiqlaysizmi?",
            parse_mode="HTML",
            reply_markup=get_confirm_keyboard()
        )


@dp.message_handler(state=ReklamaTuriState.buttons)
async def handle_buttons_input(message: types.Message, state: FSMContext):
    buttons = []
    try:
        for part in message.text.strip().split(","):
            pieces = part.strip().split("-", 1)
            if len(pieces) != 2:
                raise ValueError
            text = pieces[0].strip()
            url  = pieces[1].strip()
            if not url.startswith("http"):
                raise ValueError
            buttons.append(types.InlineKeyboardButton(text=text, url=url))
    except Exception:
        await message.reply(
            "❌ Format noto'g'ri. Qaytadan kiriting:\n"
            "<code>Tugma nomi - https://url.com</code>",
            parse_mode="HTML"
        )
        return

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(*buttons)
    await state.update_data(keyboard=keyboard)
    total = get_all_users_count()
    await message.reply(
        f"👥 Jami <b>{total}</b> ta foydalanuvchiga yuboriladi.\n\nTasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard()
    )


@dp.callback_query_handler(lambda c: c.data == "cancel_ad", state="*")
async def cancel_ad_handler(cb: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await cb.message.edit_text("❌ Reklama bekor qilindi.")
    await cb.answer()


@dp.callback_query_handler(lambda c: c.data == "confirm_ad", state="*")
async def confirm_ad_handler(cb: types.CallbackQuery, state: FSMContext):
    data       = await state.get_data()
    ad_type    = data.get("ad_type")
    ad_content = data.get("ad_content")
    keyboard   = data.get("keyboard")
    send_time  = data.get("send_time_value") if data.get("send_time") == "send_later" else None

    ad_id = len(advertisements) + 1
    ad    = Advertisement(
        ad_id=ad_id,
        message=ad_content,
        ad_type=ad_type,
        keyboard=keyboard,
        send_time=send_time,
        creator_id=cb.from_user.id
    )
    advertisements.append(ad)
    await state.finish()
    await cb.message.edit_text(
        f"🚀 Reklama #{ad_id} ishga tushirildi!\nProgress quyida ko'rsatiladi..."
    )
    await cb.answer()
    ad.task = asyncio.create_task(ad.start())


@dp.callback_query_handler(lambda c: c.data.startswith("pause_ad_"))
async def pause_ad_handler(cb: types.CallbackQuery):
    ad_id = int(cb.data.split("_")[-1])
    ad    = next((a for a in advertisements if a.ad_id == ad_id), None)
    if ad and ad.running:
        await ad.pause()
        await cb.answer(f"⏸ Reklama #{ad_id} pauza holatiga o'tdi.")
    else:
        await cb.answer("Reklama topilmadi yoki tugagan.", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("resume_ad_"))
async def resume_ad_handler(cb: types.CallbackQuery):
    ad_id = int(cb.data.split("_")[-1])
    ad    = next((a for a in advertisements if a.ad_id == ad_id), None)
    if ad and ad.paused:
        await ad.resume()
        await cb.answer(f"▶️ Reklama #{ad_id} davom ettirildi.")
    else:
        await cb.answer("Reklama topilmadi yoki pauza holatida emas.", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("stop_ad_"))
async def stop_ad_handler(cb: types.CallbackQuery):
    ad_id = int(cb.data.split("_")[-1])
    ad    = next((a for a in advertisements if a.ad_id == ad_id), None)
    if ad and ad.running:
        await ad.stop()
        await cb.answer(f"⛔ Reklama #{ad_id} to'xtatildi.")
    else:
        await cb.answer("Reklama topilmadi yoki allaqachon tugagan.", show_alert=True)


# ────────────────────────────────────────────
# Klaviaturalar
# ────────────────────────────────────────────
def get_ad_type_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✏️ Matnli",    callback_data="ad_type_text"),
        types.InlineKeyboardButton("↪️ Forward",    callback_data="ad_type_forward"),
        types.InlineKeyboardButton("🔘 Tugmali",    callback_data="ad_type_button"),
        types.InlineKeyboardButton("📎 Har qanday", callback_data="ad_type_any"),
    )
    return kb


def get_time_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⚡ Hozir",    callback_data="send_now"),
        types.InlineKeyboardButton("🕐 Keyinroq", callback_data="send_later"),
    )
    return kb


def get_cancel_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_ad"))
    return kb


def get_confirm_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Yuborish",     callback_data="confirm_ad"),
        types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_ad"),
    )
    return kb


def get_status_keyboard(ad_id: int, paused: bool = False):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if paused:
        kb.add(types.InlineKeyboardButton("▶️ Davom ettirish", callback_data=f"resume_ad_{ad_id}"))
    else:
        kb.add(types.InlineKeyboardButton("⏸ Pauza",           callback_data=f"pause_ad_{ad_id}"))
    kb.add(types.InlineKeyboardButton("⛔ To'xtatish",          callback_data=f"stop_ad_{ad_id}"))
    return kb