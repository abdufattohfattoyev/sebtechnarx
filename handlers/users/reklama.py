# handlers/reklama.py - IDEAL VERSIYA (10,000+ USER UCHUN)
import datetime
import asyncio
from data.config import ADMINS
from loader import bot, dp
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import (
    BotBlocked, ChatNotFound, RetryAfter,
    Unauthorized, MessageNotModified, TelegramAPIError
)
from aiogram.dispatcher.filters import Command

# Database import
from utils.db_api.user_database import get_all_users

# ============ KONFIGURATSIYA ============
BATCH_SIZE = 50  # Bir vaqtning o'zida 50 ta user
PROGRESS_UPDATE_INTERVAL = 50  # Har 50 tadan keyin progress yangilash
MAX_CONCURRENT_SENDS = 30  # Maksimal parallel yuborish
SEND_DELAY = 0.03  # Har bir yuborishdan keyin kutish (30ms)
RETRY_ATTEMPTS = 2  # Qayta urinish soni

# Advertisements ro'yxati
advertisements = []


class ReklamaTuriState(StatesGroup):
    tur = State()
    vaqt = State()
    time_value = State()
    content = State()
    buttons = State()


class Advertisement:
    """Optimizatsiya qilingan Advertisement class"""

    def __init__(self, ad_id, message, ad_type, keyboard=None, send_time=None, creator_id=None):
        self.ad_id = ad_id
        self.message = message
        self.ad_type = ad_type
        self.keyboard = keyboard
        self.send_time = send_time
        self.creator_id = creator_id
        self.running = False
        self.paused = False
        self.sent_count = 0
        self.failed_count = 0
        self.blocked_count = 0
        self.total_users = 0
        self.current_message = None
        self.task = None
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_SENDS)

    async def start(self):
        """Reklamani yuborishni boshlash"""
        self.running = True

        try:
            # Kechiktirilgan yuborish
            if self.send_time:
                delay = (self.send_time - datetime.datetime.now()).total_seconds()
                if delay > 0:
                    await bot.send_message(
                        chat_id=self.creator_id,
                        text=f"⏰ Reklama #{self.ad_id} {self.send_time.strftime('%d.%m.%Y %H:%M')} da yuboriladi."
                    )
                    await asyncio.sleep(delay)

            # Userlarni olish
            users = await self._get_users()

            if not users:
                await bot.send_message(
                    chat_id=self.creator_id,
                    text="❌ Bazada aktiv foydalanuvchilar yo'q!"
                )
                return

            self.total_users = len(users)

            # Status xabarini yuborish
            self.current_message = await bot.send_message(
                chat_id=self.creator_id,
                text=self._get_status_text(),
                reply_markup=get_status_keyboard(self.ad_id)
            )

            # Batch qilib yuborish
            await self._send_to_all_users(users)

            # Yakuniy status
            self.running = False
            self.paused = False
            await self.update_status_message(finished=True)

        except Exception as e:
            await bot.send_message(
                chat_id=self.creator_id,
                text=f"❌ Reklama yuborishda xatolik: {str(e)}"
            )
            self.running = False
            self.paused = False

    async def _get_users(self):
        """Userlarni olish - asinxron"""
        try:
            loop = asyncio.get_event_loop()
            users = await loop.run_in_executor(None, get_all_users)
            return users
        except Exception as e:
            print(f"❌ Userlarni olishda xato: {e}")
            return []

    async def _send_to_all_users(self, users):
        """Barcha userlarga yuborish - optimizatsiya qilingan"""
        tasks = []

        for i, user in enumerate(users):
            if not self.running:
                break

            # Pauza holatini tekshirish
            while self.paused and self.running:
                await asyncio.sleep(0.5)
                if not self.running:
                    break

            if not self.running:
                break

            # Task yaratish
            task = asyncio.create_task(self._send_to_user_safe(user))
            tasks.append(task)

            # Batch to'lsa yoki oxirgi user bo'lsa
            if len(tasks) >= BATCH_SIZE or i == len(users) - 1:
                # Barcha tasklarni kutish
                await asyncio.gather(*tasks, return_exceptions=True)
                tasks.clear()

                # Progress yangilash
                if (self.sent_count + self.failed_count) % PROGRESS_UPDATE_INTERVAL == 0:
                    await self.update_status_message()

            # Flood controldan qochish
            await asyncio.sleep(SEND_DELAY)

    async def _send_to_user_safe(self, user):
        """Bitta userga xavfsiz yuborish - semaphore bilan"""
        async with self._semaphore:
            user_id = user.get('telegram_id')

            if not user_id:
                self.failed_count += 1
                return

            # Qayta urinish mexanizmi
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    await self._send_advertisement_to_user(user_id)
                    self.sent_count += 1
                    return

                except (BotBlocked, Unauthorized):
                    # User botni bloklagan
                    self.blocked_count += 1
                    self.failed_count += 1
                    return

                except ChatNotFound:
                    # Chat topilmadi
                    self.failed_count += 1
                    return

                except RetryAfter as e:
                    # Flood control - kutish
                    if attempt < RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(e.timeout)
                        continue
                    else:
                        self.failed_count += 1
                        return

                except TelegramAPIError as e:
                    # Boshqa API xatolari
                    if attempt < RETRY_ATTEMPTS - 1:
                        await asyncio.sleep(1)
                        continue
                    else:
                        self.failed_count += 1
                        return

                except Exception as e:
                    # Kutilmagan xatolar
                    print(f"Unexpected error sending to {user_id}: {e}")
                    self.failed_count += 1
                    return

    async def _send_advertisement_to_user(self, chat_id):
        """Userga reklama yuborish"""
        message = self.message
        ad_type = self.ad_type
        keyboard = self.keyboard

        caption = message.caption if message.caption else (message.text if message.text else "")

        if ad_type == 'ad_type_text':
            await bot.send_message(chat_id=chat_id, text=caption or "Reklama")

        elif ad_type == 'ad_type_button':
            await self._send_with_keyboard(chat_id, message, keyboard, caption)

        elif ad_type == 'ad_type_forward':
            await bot.forward_message(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )

        else:
            await self._send_content(chat_id, message)

    async def _send_with_keyboard(self, chat_id, message, keyboard, caption):
        """Tugmali kontent yuborish"""
        content_type = message.content_type

        if content_type == types.ContentType.TEXT:
            await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)

        elif content_type == types.ContentType.PHOTO:
            await bot.send_photo(
                chat_id=chat_id,
                photo=message.photo[-1].file_id,
                caption=caption,
                reply_markup=keyboard
            )

        elif content_type == types.ContentType.VIDEO:
            await bot.send_video(
                chat_id=chat_id,
                video=message.video.file_id,
                caption=caption,
                reply_markup=keyboard
            )

        elif content_type == types.ContentType.DOCUMENT:
            await bot.send_document(
                chat_id=chat_id,
                document=message.document.file_id,
                caption=caption,
                reply_markup=keyboard
            )

        elif content_type == types.ContentType.ANIMATION:
            await bot.send_animation(
                chat_id=chat_id,
                animation=message.animation.file_id,
                caption=caption,
                reply_markup=keyboard
            )

        else:
            await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)

    async def _send_content(self, chat_id, message):
        """Har qanday kontentni yuborish"""
        content_type = message.content_type

        if content_type == types.ContentType.TEXT:
            await bot.send_message(chat_id=chat_id, text=message.text or "Reklama")

        elif content_type == types.ContentType.PHOTO:
            await bot.send_photo(
                chat_id=chat_id,
                photo=message.photo[-1].file_id,
                caption=message.caption
            )

        elif content_type == types.ContentType.VIDEO:
            await bot.send_video(
                chat_id=chat_id,
                video=message.video.file_id,
                caption=message.caption
            )

        elif content_type == types.ContentType.DOCUMENT:
            await bot.send_document(
                chat_id=chat_id,
                document=message.document.file_id,
                caption=message.caption
            )

        elif content_type == types.ContentType.AUDIO:
            await bot.send_audio(
                chat_id=chat_id,
                audio=message.audio.file_id,
                caption=message.caption
            )

        elif content_type == types.ContentType.ANIMATION:
            await bot.send_animation(
                chat_id=chat_id,
                animation=message.animation.file_id,
                caption=message.caption
            )

        elif content_type == types.ContentType.VOICE:
            await bot.send_voice(
                chat_id=chat_id,
                voice=message.voice.file_id,
                caption=message.caption
            )

        elif content_type == types.ContentType.VIDEO_NOTE:
            await bot.send_video_note(
                chat_id=chat_id,
                video_note=message.video_note.file_id
            )

        else:
            await bot.send_message(chat_id=chat_id, text="Reklama")

    def _get_status_text(self, finished=False, stopped=False):
        """Status textini yaratish"""
        if finished:
            status = "✅ Yakunlandi"
        elif stopped:
            status = "⛔ To'xtatildi"
        elif self.paused:
            status = "⏸️ Pauza"
        else:
            status = "⏳ Yuborilmoqda..."

        progress_percent = 0
        if self.total_users > 0:
            progress_percent = ((self.sent_count + self.failed_count) / self.total_users) * 100

        progress_bar = "█" * int(progress_percent / 5) + "░" * (20 - int(progress_percent / 5))

        text = (
            f"📤 <b>Reklama #{self.ad_id}</b>\n\n"
            f"[{progress_bar}] {progress_percent:.1f}%\n\n"
            f"✅ Yuborildi: <b>{self.sent_count:,}</b>\n"
            f"❌ Yuborilmadi: <b>{self.failed_count:,}</b>\n"
        )

        if self.blocked_count > 0:
            text += f"🚫 Bloklagan: <b>{self.blocked_count:,}</b>\n"

        text += (
            f"📊 Jami: <b>{self.sent_count + self.failed_count:,}</b> / <b>{self.total_users:,}</b>\n\n"
            f"Status: {status}"
        )

        return text

    async def pause(self):
        """Pauzaga qo'yish"""
        self.paused = True
        await self.update_status_message()

    async def resume(self):
        """Davom ettirish"""
        self.paused = False
        await self.update_status_message()

    async def stop(self):
        """To'xtatish"""
        self.running = False
        self.paused = False

        # Taskni bekor qilish
        if self.task and not self.task.done():
            self.task.cancel()

        await self.update_status_message(stopped=True)

    async def update_status_message(self, finished=False, stopped=False):
        """Status xabarini yangilash"""
        if not self.current_message:
            return

        text = self._get_status_text(finished, stopped)

        try:
            if finished or stopped:
                await self.current_message.edit_text(
                    text,
                    reply_markup=None,
                    parse_mode="HTML"
                )
            else:
                await self.current_message.edit_text(
                    text,
                    reply_markup=get_status_keyboard(self.ad_id, self.paused),
                    parse_mode="HTML"
                )
        except MessageNotModified:
            pass
        except Exception as e:
            print(f"Status yangilashda xato: {e}")


# ============ HANDLERLAR ============

@dp.message_handler(Command("reklama"), state="*", user_id=ADMINS)
@dp.message_handler(lambda m: m.text == "📣 Reklama", state="*", user_id=ADMINS)
async def reklama_handler(message: types.Message, state: FSMContext):
    """Reklama yuborish boshlash"""
    await state.finish()
    await ReklamaTuriState.tur.set()

    await message.answer(
        "📢 <b>REKLAMA YUBORISH</b>\n\n"
        "Quyidagi reklama turlaridan birini tanlang:",
        reply_markup=get_ad_type_keyboard(),
        parse_mode="HTML"
    )


@dp.callback_query_handler(
    lambda c: c.data in ["ad_type_text", "ad_type_forward", "ad_type_button", "ad_type_any"],
    state=ReklamaTuriState.tur,
    user_id=ADMINS
)
async def handle_ad_type(callback_query: types.CallbackQuery, state: FSMContext):
    """Reklama turini tanlash"""
    await state.update_data(ad_type=callback_query.data)
    await ReklamaTuriState.vaqt.set()

    ad_type_names = {
        'ad_type_text': 'Matnli',
        'ad_type_forward': 'Forward',
        'ad_type_button': 'Tugmali',
        'ad_type_any': 'Har qanday kontent'
    }

    await callback_query.message.edit_text(
        f"✅ Tanlandi: <b>{ad_type_names.get(callback_query.data)}</b>\n\n"
        "⏰ Reklama yuborish vaqtini tanlang:",
        reply_markup=get_time_keyboard(),
        parse_mode="HTML"
    )
    await callback_query.answer()


@dp.callback_query_handler(
    lambda c: c.data in ["send_now", "send_later"],
    state=ReklamaTuriState.vaqt,
    user_id=ADMINS
)
async def handle_send_time(callback_query: types.CallbackQuery, state: FSMContext):
    """Yuborish vaqtini tanlash"""
    await state.update_data(send_time=callback_query.data)

    if callback_query.data == "send_later":
        await ReklamaTuriState.time_value.set()
        await callback_query.message.edit_text(
            "⏰ <b>Vaqtni kiriting</b>\n\n"
            "Format: <code>HH:MM</code>\n"
            "Masalan: <code>14:30</code>\n\n"
            "<i>Agar bugun ushbu vaqt o'tgan bo'lsa, ertaga yuboriladi.</i>",
            parse_mode="HTML"
        )
    else:
        await ReklamaTuriState.content.set()
        await callback_query.message.edit_text(
            "📝 <b>Reklama kontentini yuboring:</b>\n\n"
            "• Matn, rasm, video yoki boshqa kontent\n"
            "• Forward ham qilishingiz mumkin",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )

    await callback_query.answer()


@dp.message_handler(state=ReklamaTuriState.time_value, user_id=ADMINS)
async def handle_time_input(message: types.Message, state: FSMContext):
    """Vaqt kiritish"""
    time_value = message.text.strip()

    try:
        send_time = datetime.datetime.strptime(time_value, '%H:%M')
        now = datetime.datetime.now()
        send_time = send_time.replace(year=now.year, month=now.month, day=now.day)

        if send_time < now:
            send_time += datetime.timedelta(days=1)
            tomorrow_text = " (ertaga)"
        else:
            tomorrow_text = " (bugun)"

        await state.update_data(send_time_value=send_time)
        await ReklamaTuriState.content.set()

        await message.reply(
            f"✅ Vaqt: <b>{send_time.strftime('%H:%M')}{tomorrow_text}</b>\n\n"
            "📝 Endi reklama kontentini yuboring:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )

    except ValueError:
        await message.reply(
            "❌ <b>Vaqt formati noto'g'ri!</b>\n\n"
            "To'g'ri format: <code>HH:MM</code>\n"
            "Masalan: <code>14:30</code>",
            parse_mode="HTML"
        )


@dp.message_handler(
    state=ReklamaTuriState.content,
    content_types=types.ContentType.ANY,
    user_id=ADMINS
)
async def handle_content(message: types.Message, state: FSMContext):
    """Kontent qabul qilish"""
    data = await state.get_data()
    ad_type = data.get('ad_type')

    if ad_type == 'ad_type_button':
        await state.update_data(ad_content=message)
        await ReklamaTuriState.buttons.set()
        await message.reply(
            "🔘 <b>Tugmalarni kiriting:</b>\n\n"
            "Format: <code>Matn - URL</code>\n\n"
            "Bir nechta tugma:\n"
            "<code>Telegram - https://t.me,\n"
            "Website - https://example.com</code>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    else:
        await state.update_data(ad_content=message)
        await message.reply(
            "✅ Kontent qabul qilindi!\n\n"
            "Yuborishni tasdiqlaysizmi?",
            reply_markup=get_confirm_keyboard()
        )


@dp.message_handler(state=ReklamaTuriState.buttons, user_id=ADMINS)
async def handle_buttons_input(message: types.Message, state: FSMContext):
    """Tugmalarni qabul qilish"""
    buttons_text = message.text.strip()
    buttons = []

    try:
        for button_data in buttons_text.split(','):
            parts = button_data.strip().split(' - ')
            if len(parts) != 2:
                raise ValueError("Format noto'g'ri")

            text = parts[0].strip()
            url = parts[1].strip()

            if not text or not url:
                raise ValueError("Bo'sh matn yoki URL")

            buttons.append(types.InlineKeyboardButton(text=text, url=url))

        if not buttons:
            raise ValueError("Tugmalar yo'q")

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(*buttons)

        await state.update_data(keyboard=keyboard)
        await message.reply(
            "✅ Tugmalar qo'shildi!\n\n"
            "Yuborishni tasdiqlaysizmi?",
            reply_markup=get_confirm_keyboard()
        )

    except Exception:
        await message.reply(
            "❌ <b>Format noto'g'ri!</b>\n\n"
            "To'g'ri:\n"
            "<code>Matn1 - URL1, Matn2 - URL2</code>",
            parse_mode="HTML"
        )


@dp.callback_query_handler(lambda c: c.data == "cancel_ad", state='*', user_id=ADMINS)
async def cancel_ad_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Bekor qilish"""
    await state.finish()
    await callback_query.message.edit_text("❌ Bekor qilindi")
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "confirm_ad", state='*', user_id=ADMINS)
async def confirm_ad_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Tasdiqlash va yuborish"""
    data = await state.get_data()

    ad_id = len(advertisements) + 1
    advertisement = Advertisement(
        ad_id=ad_id,
        message=data.get('ad_content'),
        ad_type=data.get('ad_type'),
        keyboard=data.get('keyboard'),
        send_time=data.get('send_time_value') if data.get('send_time') == 'send_later' else None,
        creator_id=callback_query.from_user.id
    )

    advertisements.append(advertisement)
    await state.finish()

    if advertisement.send_time:
        await callback_query.message.edit_text(
            f"✅ Reklama #{ad_id} jadvalga qo'shildi!\n\n"
            f"⏰ Vaqt: {advertisement.send_time.strftime('%d.%m.%Y %H:%M')}"
        )
    else:
        await callback_query.message.edit_text(
            f"✅ Reklama #{ad_id} boshlandi!"
        )

    advertisement.task = asyncio.create_task(advertisement.start())
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("pause_ad_"), user_id=ADMINS)
async def pause_ad_handler(callback_query: types.CallbackQuery):
    """Pauzaga qo'yish"""
    ad_id = int(callback_query.data.split("_")[-1])
    ad = next((a for a in advertisements if a.ad_id == ad_id), None)

    if ad and ad.running:
        await ad.pause()
        await callback_query.answer("⏸️ Pauza")
    else:
        await callback_query.answer("❌ Topilmadi", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("resume_ad_"), user_id=ADMINS)
async def resume_ad_handler(callback_query: types.CallbackQuery):
    """Davom ettirish"""
    ad_id = int(callback_query.data.split("_")[-1])
    ad = next((a for a in advertisements if a.ad_id == ad_id), None)

    if ad and ad.paused:
        await ad.resume()
        await callback_query.answer("▶️ Davom ettirildi")
    else:
        await callback_query.answer("❌ Topilmadi", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("stop_ad_"), user_id=ADMINS)
async def stop_ad_handler(callback_query: types.CallbackQuery):
    """To'xtatish"""
    ad_id = int(callback_query.data.split("_")[-1])
    ad = next((a for a in advertisements if a.ad_id == ad_id), None)

    if ad and ad.running:
        await ad.stop()
        await callback_query.answer("⛔ To'xtatildi")
    else:
        await callback_query.answer("❌ Topilmadi", show_alert=True)


# ============ KLAVIATURALAR ============

def get_cancel_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_ad"))
    return keyboard


def get_confirm_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_ad"))
    keyboard.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_ad"))
    return keyboard


def get_ad_type_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("📝 Matnli", callback_data="ad_type_text"),
        types.InlineKeyboardButton("↗️ Forward", callback_data="ad_type_forward")
    )
    keyboard.add(
        types.InlineKeyboardButton("🔘 Tugmali", callback_data="ad_type_button"),
        types.InlineKeyboardButton("📦 Har qanday", callback_data="ad_type_any")
    )
    return keyboard


def get_time_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("⚡ Hozir", callback_data="send_now"))
    keyboard.add(types.InlineKeyboardButton("⏰ Keyinroq", callback_data="send_later"))
    return keyboard


def get_status_keyboard(ad_id, paused=False):
    keyboard = types.InlineKeyboardMarkup()

    if paused:
        keyboard.add(types.InlineKeyboardButton("▶️ Davom", callback_data=f"resume_ad_{ad_id}"))
    else:
        keyboard.add(types.InlineKeyboardButton("⏸️ Pauza", callback_data=f"pause_ad_{ad_id}"))

    keyboard.add(types.InlineKeyboardButton("⛔ To'xtatish", callback_data=f"stop_ad_{ad_id}"))
    return keyboard