# reklama.py
import datetime
import asyncio
from data.config import ADMINS
from loader import bot, dp
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import BotBlocked, ChatNotFound, RetryAfter, Unauthorized, MessageNotModified
from aiogram.dispatcher.filters import Command

# Stats database import
from utils.db_api.stats_database import get_all_users

# Reklama yuborish jarayonlarini saqlash uchun ro'yxat
advertisements = []


class ReklamaTuriState(StatesGroup):
    tur = State()
    vaqt = State()
    time_value = State()
    content = State()
    buttons = State()


class Advertisement:
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
        self.total_users = 0
        self.current_message = None
        self.task = None

    async def start(self):
        self.running = True

        # Agar kechiktirilgan yuborish bo'lsa
        if self.send_time:
            delay = (self.send_time - datetime.datetime.now()).total_seconds()
            if delay > 0:
                await bot.send_message(
                    chat_id=self.creator_id,
                    text=f"⏰ Reklama #{self.ad_id} {self.send_time.strftime('%H:%M')} da yuboriladi."
                )
                await asyncio.sleep(delay)

        # Foydalanuvchilarni olish
        try:
            users = get_all_users()
            self.total_users = len(users)
        except Exception as e:
            await bot.send_message(
                chat_id=self.creator_id,
                text=f"❌ Foydalanuvchilarni olishda xatolik: {str(e)}"
            )
            return

        if self.total_users == 0:
            await bot.send_message(
                chat_id=self.creator_id,
                text="❌ Bazada foydalanuvchilar yo'q!"
            )
            return

        # Status xabarini yuborish
        self.current_message = await bot.send_message(
            chat_id=self.creator_id,
            text=f"📤 Reklama #{self.ad_id} yuborish boshlandi\n\n"
                 f"✅ Yuborilgan: {self.sent_count}\n"
                 f"❌ Yuborilmagan: {self.failed_count}\n"
                 f"📊 Jami: {self.sent_count + self.failed_count}/{self.total_users}\n\n"
                 f"⏳ Status: Davom etmoqda...",
            reply_markup=get_status_keyboard(self.ad_id)
        )

        # Har bir foydalanuvchiga yuborish
        for user in users:
            if not self.running:
                break

            # Pauza holatini tekshirish
            while self.paused:
                await asyncio.sleep(1)
                if not self.running:
                    break

            if not self.running:
                break

            try:
                # user dict dan user_id ni olish
                user_id = user.get('user_id')
                if not user_id:
                    self.failed_count += 1
                    continue

                await send_advertisement_to_user(user_id, self)
                self.sent_count += 1

            except (BotBlocked, ChatNotFound, Unauthorized):
                self.failed_count += 1
            except RetryAfter as e:
                await asyncio.sleep(e.timeout)
                # Qayta urinish
                try:
                    await send_advertisement_to_user(user_id, self)
                    self.sent_count += 1
                except:
                    self.failed_count += 1
            except Exception as e:
                self.failed_count += 1
                print(f"Yuborishda xatolik: {e}")

            # Har 10 ta yuborilgandan keyin statusni yangilash
            if (self.sent_count + self.failed_count) % 10 == 0:
                await self.update_status_message()

            # Flood controldan qochish
            await asyncio.sleep(0.05)

        # Yakuniy status
        self.running = False
        self.paused = False
        await self.update_status_message(finished=True)

    async def pause(self):
        self.paused = True
        await self.update_status_message()

    async def resume(self):
        self.paused = False
        await self.update_status_message()

    async def stop(self):
        self.running = False
        self.paused = False
        await self.update_status_message(stopped=True)

    async def update_status_message(self, finished=False, stopped=False):
        if finished:
            status = "✅ Yakunlandi"
        elif stopped:
            status = "⛔ To'xtatildi"
        elif self.paused:
            status = "⏸️ Pauza holatida"
        else:
            status = "⏳ Davom etmoqda..."

        text = (f"📤 Reklama #{self.ad_id}\n\n"
                f"✅ Yuborilgan: {self.sent_count}\n"
                f"❌ Yuborilmagan: {self.failed_count}\n"
                f"📊 Jami: {self.sent_count + self.failed_count}/{self.total_users}\n\n"
                f"Status: {status}")

        if self.current_message:
            try:
                if finished or stopped:
                    await self.current_message.edit_text(text, reply_markup=None)
                else:
                    await self.current_message.edit_text(
                        text,
                        reply_markup=get_status_keyboard(self.ad_id, self.paused)
                    )
            except MessageNotModified:
                pass
            except Exception as e:
                print(f"Status yangilashda xatolik: {e}")


async def send_advertisement_to_user(chat_id, advertisement: Advertisement):
    """Foydalanuvchiga reklama yuborish"""
    message = advertisement.message
    ad_type = advertisement.ad_type
    keyboard = advertisement.keyboard

    # Caption yoki text olish
    caption = message.caption if message.caption else (message.text if message.text else "")

    try:
        if ad_type == 'ad_type_text':
            # Faqat matn
            await bot.send_message(chat_id=chat_id, text=caption or "Reklama")

        elif ad_type == 'ad_type_button':
            # Tugmali kontent
            await handle_content_with_keyboard(chat_id, message, keyboard, caption)

        elif ad_type == 'ad_type_forward':
            # Forward
            await bot.forward_message(
                chat_id=chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )

        elif ad_type == 'ad_type_any':
            # Har qanday kontent
            await handle_non_text_content(chat_id, message)

        else:
            # Default
            await handle_non_text_content(chat_id, message)

    except Exception as e:
        raise e


async def handle_content_with_keyboard(chat_id, message, keyboard, caption):
    """Tugmali kontent yuborish"""
    try:
        if message.content_type == types.ContentType.TEXT:
            await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)

        elif message.content_type == types.ContentType.PHOTO:
            await bot.send_photo(
                chat_id=chat_id,
                photo=message.photo[-1].file_id,
                caption=caption,
                reply_markup=keyboard
            )

        elif message.content_type == types.ContentType.VIDEO:
            await bot.send_video(
                chat_id=chat_id,
                video=message.video.file_id,
                caption=caption,
                reply_markup=keyboard
            )

        elif message.content_type == types.ContentType.DOCUMENT:
            await bot.send_document(
                chat_id=chat_id,
                document=message.document.file_id,
                caption=caption,
                reply_markup=keyboard
            )

        elif message.content_type == types.ContentType.AUDIO:
            await bot.send_audio(
                chat_id=chat_id,
                audio=message.audio.file_id,
                caption=caption,
                reply_markup=keyboard
            )

        elif message.content_type == types.ContentType.ANIMATION:
            await bot.send_animation(
                chat_id=chat_id,
                animation=message.animation.file_id,
                caption=caption,
                reply_markup=keyboard
            )

        else:
            await bot.send_message(chat_id=chat_id, text=caption, reply_markup=keyboard)

    except Exception as e:
        raise e


async def handle_non_text_content(chat_id, message):
    """Har qanday kontentni yuborish"""
    try:
        if message.content_type == types.ContentType.TEXT:
            text = message.text or "Reklama"
            await bot.send_message(chat_id=chat_id, text=text)

        elif message.content_type == types.ContentType.PHOTO:
            await bot.send_photo(
                chat_id=chat_id,
                photo=message.photo[-1].file_id,
                caption=message.caption
            )

        elif message.content_type == types.ContentType.VIDEO:
            await bot.send_video(
                chat_id=chat_id,
                video=message.video.file_id,
                caption=message.caption
            )

        elif message.content_type == types.ContentType.DOCUMENT:
            await bot.send_document(
                chat_id=chat_id,
                document=message.document.file_id,
                caption=message.caption
            )

        elif message.content_type == types.ContentType.AUDIO:
            await bot.send_audio(
                chat_id=chat_id,
                audio=message.audio.file_id,
                caption=message.caption
            )

        elif message.content_type == types.ContentType.ANIMATION:
            await bot.send_animation(
                chat_id=chat_id,
                animation=message.animation.file_id,
                caption=message.caption
            )

        elif message.content_type == types.ContentType.VOICE:
            await bot.send_voice(
                chat_id=chat_id,
                voice=message.voice.file_id,
                caption=message.caption
            )

        elif message.content_type == types.ContentType.VIDEO_NOTE:
            await bot.send_video_note(
                chat_id=chat_id,
                video_note=message.video_note.file_id
            )

        else:
            await bot.send_message(
                chat_id=chat_id,
                text="Reklama (kontent qo'llab-quvvatlanmaydi)"
            )

    except Exception as e:
        raise e


async def check_admin_permission(telegram_id: int):
    """Admin ekanligini tekshirish"""
    return telegram_id in ADMINS


@dp.message_handler(Command("reklama"), state="*")
@dp.message_handler(lambda m: m.text == "📣 Reklama", state="*")
async def reklama_handler(message: types.Message, state: FSMContext):
    """Reklama yuborish boshlash"""
    telegram_id = message.from_user.id

    if not await check_admin_permission(telegram_id):
        await message.reply("❌ Sizda reklama yuborish uchun ruxsat yo'q!")
        return

    # Oldingi holatni tozalash
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
    state=ReklamaTuriState.tur
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


@dp.callback_query_handler(
    lambda c: c.data in ["send_now", "send_later"],
    state=ReklamaTuriState.vaqt
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
            "• Matn, rasm, video yoki boshqa kontent yuborishingiz mumkin\n"
            "• Forward ham qilishingiz mumkin",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )


@dp.message_handler(state=ReklamaTuriState.time_value)
async def handle_time_input(message: types.Message, state: FSMContext):
    """Vaqt kiritish"""
    time_value = message.text.strip()

    try:
        send_time = datetime.datetime.strptime(time_value, '%H:%M')
        now = datetime.datetime.now()
        send_time = send_time.replace(year=now.year, month=now.month, day=now.day)

        # Agar vaqt o'tgan bo'lsa, ertaga o'tkazish
        if send_time < now:
            send_time += datetime.timedelta(days=1)
            tomorrow_text = " (ertaga)"
        else:
            tomorrow_text = " (bugun)"

        await state.update_data(send_time_value=send_time)
        await ReklamaTuriState.content.set()

        await message.reply(
            f"✅ Vaqt o'rnatildi: <b>{send_time.strftime('%H:%M')}{tomorrow_text}</b>\n\n"
            "📝 Endi reklama kontentini yuboring:",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )

    except ValueError:
        await message.reply(
            "❌ <b>Vaqt formati noto'g'ri!</b>\n\n"
            "To'g'ri format: <code>HH:MM</code>\n"
            "Masalan: <code>14:30</code> yoki <code>09:15</code>",
            parse_mode="HTML"
        )


@dp.message_handler(state=ReklamaTuriState.content, content_types=types.ContentType.ANY)
async def rek_state(message: types.Message, state: FSMContext):
    """Kontent qabul qilish"""
    telegram_id = message.from_user.id

    if not await check_admin_permission(telegram_id):
        await message.reply("❌ Ruxsat yo'q!")
        await state.finish()
        return

    data = await state.get_data()
    ad_type = data.get('ad_type')

    if ad_type == 'ad_type_button':
        # Tugmali reklama uchun tugmalarni so'rash
        await state.update_data(ad_content=message)
        await ReklamaTuriState.buttons.set()
        await message.reply(
            "🔘 <b>Tugmalarni kiriting:</b>\n\n"
            "Format: <code>Tugma matni - URL</code>\n\n"
            "Bir nechta tugma uchun vergul bilan ajrating:\n"
            "<code>Telegram - https://t.me, "
            "Website - https://example.com</code>",
            reply_markup=get_cancel_keyboard(),
            parse_mode="HTML"
        )
    else:
        # Boshqa turlar uchun to'g'ridan-to'g'ri tasdiqlash
        await state.update_data(ad_content=message)
        await message.reply(
            "✅ Kontent qabul qilindi!\n\n"
            "Reklamani yuborishni tasdiqlaysizmi?",
            reply_markup=get_confirm_keyboard()
        )


@dp.message_handler(state=ReklamaTuriState.buttons)
async def handle_buttons_input(message: types.Message, state: FSMContext):
    """Tugmalarni qabul qilish"""
    buttons_text = message.text.strip()
    buttons = []

    try:
        for button_data in buttons_text.split(','):
            parts = button_data.strip().split(' - ')
            if len(parts) != 2:
                raise ValueError("Incorrect format")

            text = parts[0].strip()
            url = parts[1].strip()

            if not text or not url:
                raise ValueError("Empty text or URL")

            buttons.append(types.InlineKeyboardButton(text=text, url=url))

        if not buttons:
            raise ValueError("No buttons")

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(*buttons)

        await state.update_data(keyboard=keyboard)
        await message.reply(
            "✅ Tugmalar qo'shildi!\n\n"
            "Reklamani yuborishni tasdiqlaysizmi?",
            reply_markup=get_confirm_keyboard()
        )

    except Exception as e:
        await message.reply(
            "❌ <b>Tugmalar formati noto'g'ri!</b>\n\n"
            "To'g'ri format:\n"
            "<code>Tugma1 - URL1, Tugma2 - URL2</code>\n\n"
            "Masalan:\n"
            "<code>Telegram - https://t.me, "
            "Website - https://example.com</code>",
            parse_mode="HTML"
        )


@dp.callback_query_handler(lambda c: c.data == "cancel_ad", state='*')
async def cancel_ad_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Reklamani bekor qilish"""
    await state.finish()
    await callback_query.message.edit_text("❌ Reklama yuborish bekor qilindi")
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "confirm_ad", state='*')
async def confirm_ad_handler(callback_query: types.CallbackQuery, state: FSMContext):
    """Reklamani tasdiqlash va yuborish"""
    data = await state.get_data()
    ad_type = data.get('ad_type')
    ad_content = data.get('ad_content')
    keyboard = data.get('keyboard')
    send_time = data.get('send_time_value') if data.get('send_time') == 'send_later' else None

    ad_id = len(advertisements) + 1

    advertisement = Advertisement(
        ad_id=ad_id,
        message=ad_content,
        ad_type=ad_type,
        keyboard=keyboard,
        send_time=send_time,
        creator_id=callback_query.from_user.id
    )

    advertisements.append(advertisement)
    await state.finish()

    if send_time:
        await callback_query.message.edit_text(
            f"✅ Reklama #{ad_id} jadvalga qo'shildi!\n\n"
            f"⏰ Yuborish vaqti: {send_time.strftime('%d.%m.%Y %H:%M')}"
        )
    else:
        await callback_query.message.edit_text(
            f"✅ Reklama #{ad_id} yuborish boshlandi!"
        )

    # Asinxron yuborish
    advertisement.task = asyncio.create_task(advertisement.start())
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("pause_ad_"))
async def pause_ad_handler(callback_query: types.CallbackQuery):
    """Reklamani pauza qilish"""
    ad_id = int(callback_query.data.split("_")[-1])
    advertisement = next((ad for ad in advertisements if ad.ad_id == ad_id), None)

    if advertisement and advertisement.running:
        await advertisement.pause()
        await callback_query.answer("⏸️ Reklama pauza qilindi")
    else:
        await callback_query.answer("❌ Reklama topilmadi yoki ishlamayapti", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("resume_ad_"))
async def resume_ad_handler(callback_query: types.CallbackQuery):
    """Reklamani davom ettirish"""
    ad_id = int(callback_query.data.split("_")[-1])
    advertisement = next((ad for ad in advertisements if ad.ad_id == ad_id), None)

    if advertisement and advertisement.paused:
        await advertisement.resume()
        await callback_query.answer("▶️ Reklama davom ettirildi")
    else:
        await callback_query.answer("❌ Reklama topilmadi yoki pauza holatida emas", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("stop_ad_"))
async def stop_ad_handler(callback_query: types.CallbackQuery):
    """Reklamani to'xtatish"""
    ad_id = int(callback_query.data.split("_")[-1])
    advertisement = next((ad for ad in advertisements if ad.ad_id == ad_id), None)

    if advertisement and advertisement.running:
        await advertisement.stop()
        await callback_query.answer("⛔ Reklama to'xtatildi")
    else:
        await callback_query.answer("❌ Reklama topilmadi yoki allaqachon to'xtagan", show_alert=True)


# ============ KLAVIATURALAR ============

def get_cancel_keyboard():
    """Bekor qilish klaviaturasi"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_ad"))
    return keyboard


def get_confirm_keyboard():
    """Tasdiqlash klaviaturasi"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm_ad"))
    keyboard.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_ad"))
    return keyboard


def get_ad_type_keyboard():
    """Reklama turi klaviaturasi"""
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
    """Vaqt klaviaturasi"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("⚡ Hozir yuborish", callback_data="send_now"))
    keyboard.add(types.InlineKeyboardButton("⏰ Keyinroq yuborish", callback_data="send_later"))
    return keyboard


def get_status_keyboard(ad_id, paused=False):
    """Status klaviaturasi"""
    keyboard = types.InlineKeyboardMarkup()

    if paused:
        keyboard.add(types.InlineKeyboardButton("▶️ Davom ettirish", callback_data=f"resume_ad_{ad_id}"))
    else:
        keyboard.add(types.InlineKeyboardButton("⏸️ Pauza", callback_data=f"pause_ad_{ad_id}"))

    keyboard.add(types.InlineKeyboardButton("⛔ To'xtatish", callback_data=f"stop_ad_{ad_id}"))
    return keyboard