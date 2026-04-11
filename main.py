import asyncio
import os
import time
import uuid
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from xui_api import XUI

try:
    from aiocryptopay import AioCryptoPay, Networks
    CRYPTOPAY_AVAILABLE = True
except ImportError:
    CRYPTOPAY_AVAILABLE = False

load_dotenv()

# --- КОНФИГ ---
ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy" 
CHANNEL_URL = "https://t.me/kent_proxy"
MAX_DEVICES = 5

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
xui = XUI()

crypto = None
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)

class FormStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_admin_id = State()

# --- ПРОВЕРКА ПОДПИСКИ ---
async def check_subscription(user_id):
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

# --- КЛАВИАТУРЫ ---

def main_menu_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(
        types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton(text="⚙️ Инструкции", callback_data="help")
    )
    builder.row(types.InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()

def sub_check_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
    builder.row(types.InlineKeyboardButton(text="✅ Я подписался", callback_data="start_over"))
    return builder.as_markup()

def back_to_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ В главное меню", callback_data="start_over"))
    return builder.as_markup()

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery, state: FSMContext):
    user_id = event.from_user.id
    await state.clear()
    
    if not await check_subscription(user_id):
        text = "<b>🚫 Доступ ограничен!</b>\n\nДля использования бота подпишитесь на наш канал."
        kb = sub_check_kb()
        return await (event.answer(text, reply_markup=kb) if isinstance(event, types.Message) else event.message.edit_text(text, reply_markup=kb))

    text = "<b>🚀 KENTVPN — Твой личный доступ без границ!</b>\n\nВыберите действие:"
    kb = main_menu_kb(user_id)
    return await (event.answer(text, reply_markup=kb) if isinstance(event, types.Message) else event.message.edit_text(text, reply_markup=kb))

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not await check_subscription(user_id):
        return await callback.answer("Сначала подпишитесь на канал!", show_alert=True)
        
    devices = await db.get_user_devices(user_id)
    if len(devices) >= MAX_DEVICES and user_id not in ADMIN_IDS:
        return await callback.message.edit_text(
            f"<b>⚠️ Лимит устройств!</b>\n\nВы уже создали {MAX_DEVICES} подписок. "
            "Для расширения лимита напишите в поддержку.",
            reply_markup=back_to_main_kb()
        )

    text = (
        "<b>💎 KENTVPN Premium (30 дней)</b>\n\n"
        "✅ Скорость до 1 Гбит/с\n"
        "✅ Протокол VLESS + Reality (не блокируется)\n"
        "✅ Доступ ко всем сайтам\n"
        "⚠️ <i>Ограничение: до 5 устройств на аккаунт</i>\n\n"
        "💰 <b>Цена: 1 USDT</b>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить 1 USDT", callback_data="pay_crypto"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_crypto")
async def start_pay(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if user_id in ADMIN_IDS:
        dev_name = f"Admin_Device_{int(time.time())}"
        u_uuid = xui.add_client(user_id, dev_name)
        if u_uuid:
            await db.add_device(user_id, dev_name, u_uuid, expiry_days=365)
            link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=dev_name)
            await callback.message.answer(f"👑 <b>Бесплатно для админа:</b>\n<code>{link}</code>")
        return

    await callback.message.answer("🏷 Введите название устройства (например: iPhone):")
    await state.set_state(FormStates.waiting_for_name)

@dp.message(FormStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if not crypto: return await message.answer("Оплата недоступна.")
    await state.update_data(dname=message.text)
    
    invoice = await crypto.create_invoice(asset='USDT', amount=1, payload=str(uuid.uuid4()))
    pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'pay_url', None)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔗 Оплатить 1 USDT", url=pay_url))
    builder.row(types.InlineKeyboardButton(text="✅ Проверить", callback_data=f"check_{invoice.invoice_id}"))
    await message.answer(f"📦 <b>Устройство:</b> {message.text}\nНажмите кнопку для оплаты:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_"))
async def check_p(callback: types.CallbackQuery, state: FSMContext):
    inv_id = int(callback.data.split("_")[1])
    invoices = await crypto.get_invoices(invoice_ids=[inv_id])
    if invoices and invoices[0].status == 'paid':
        data = await state.get_data()
        dname = data.get('dname', 'Device')
        u_uuid = xui.add_client(callback.from_user.id, dname)
        await db.add_device(callback.from_user.id, dname, u_uuid, expiry_days=30)
        link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=dname)
        await callback.message.answer(f"✅ Оплачено!\nКлюч: <code>{link}</code>", reply_markup=back_to_main_kb())
        await state.clear()
    else:
        await callback.answer("Оплата не найдена", show_alert=True)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not await check_subscription(user_id):
        return await callback.answer("Сначала подпишитесь на канал!", show_alert=True)

    if await db.check_trial(user_id):
        return await callback.answer("❌ Вы уже использовали пробный период!", show_alert=True)
    
    u_uuid = xui.add_client(user_id, f"Trial_{user_id}")
    if u_uuid:
        await db.add_device(user_id, f"Trial_{user_id}", u_uuid, expiry_days=2)
        await db.set_trial_used(user_id)
        link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=f"Trial_{user_id}")
        await callback.message.answer(f"🎁 <b>Тест на 2 дня:</b>\n<code>{link}</code>", reply_markup=back_to_main_kb())
    else:
        await callback.answer("Ошибка сервера", show_alert=True)

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ Выдать VPN бесплатно", callback_data="admin_give"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text("<b>👑 Админ-панель</b>", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_give")
async def admin_give(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID пользователя:")
    await state.set_state(FormStates.waiting_for_admin_id)

@dp.message(FormStates.waiting_for_admin_id)
async def admin_give_res(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        t_id = int(message.text)
        u_uuid = xui.add_client(t_id, "Gift")
        await db.add_device(t_id, "Gift", u_uuid, expiry_days=365)
        await message.answer(f"✅ Выдано юзеру {t_id}")
    except: await message.answer("Ошибка ID")
    await state.clear()

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    text = f"<b>👤 Профиль</b>\nID: <code>{callback.from_user.id}</code>\n\n<b>Ваши ключи ({len(devices)}/{MAX_DEVICES}):</b>\n"
    for d in devices:
        link = os.getenv("VLESS_TEMPLATE").format(uuid=d['uuid'], device_name=d['device_name'])
        text += f"— {d['device_name']}: <code>{link}</code>\n"
    await callback.message.edit_text(text if devices else "У вас нет активных ключей", reply_markup=back_to_main_kb())

@dp.callback_query(F.data == "help")
async def help_sect(callback: types.CallbackQuery):
    await callback.message.edit_text("<b>⚙️ Инструкция:</b>\n1. Скачайте v2rayNG/V2Box\n2. Скопируйте ключ\n3. Добавьте в приложение.", reply_markup=back_to_main_kb())

@dp.callback_query(F.data == "support")
async def support_sect(callback: types.CallbackQuery):
    await callback.message.edit_text("<b>🆘 Поддержка:</b> @твой_логин", reply_markup=back_to_main_kb())

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
