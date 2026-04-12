import asyncio
import os
import time
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

# Интеграция оплаты
try:
    from aiocryptopay import AioCryptoPay, Networks
    CRYPTOPAY_AVAILABLE = True
except ImportError:
    CRYPTOPAY_AVAILABLE = False

load_dotenv()

ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy" 
CHANNEL_URL = "https://t.me/kent_proxy"
MAX_DEVICES = 5

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

crypto = None
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)

class FormStates(StatesGroup):
    waiting_for_name = State()

async def check_subscription(user_id):
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

def main_menu_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"))
    builder.row(types.InlineKeyboardButton(text="⚙️ Инструкции", callback_data="help"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel"))
    return builder.as_markup()

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Проверить", callback_data="start_over"))
        txt = "<b>🚫 Ошибка!</b>\nСначала подпишись на наш канал."
        if isinstance(event, types.Message): return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    txt = "<b>🚀 KENTVPN — Твой личный обход блокировок!</b>"
    kb = main_menu_kb(user_id)
    if isinstance(event, types.Message): await event.answer(txt, reply_markup=kb)
    else: await event.message.edit_text(txt, reply_markup=kb)

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    txt = "<b>💎 Premium Подписка (30 дней)</b>\n\n💰 Цена: 1 USDT\nПосле оплаты ты получишь ссылку-подписку."
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить 1 USDT", callback_data="pay_crypto"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_crypto")
async def start_pay(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Как назовем устройство? (например: iPhone)")
    await state.set_state(FormStates.waiting_for_name)

@dp.message(FormStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(dname=message.text)
    invoice = await crypto.create_invoice(asset='USDT', amount=1)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔗 Оплатить через CryptoBot", url=invoice.bot_invoice_url))
    builder.row(types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_{invoice.invoice_id}"))
    await message.answer(f"Счет на 1 USDT для <b>{message.text}</b> готов:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_"))
async def check_p(callback: types.CallbackQuery, state: FSMContext):
    inv_id = int(callback.data.split("_")[1])
    invoices = await crypto.get_invoices(invoice_ids=[inv_id])
    if invoices and invoices[0].status == 'paid':
        data = await state.get_data()
        sub_id = xui.add_client(callback.from_user.id, data['dname'], days=30)
        if sub_id:
            await db.add_device(callback.from_user.id, data['dname'], sub_id, 30)
            link = os.getenv("VLESS_TEMPLATE").format(sub_id=sub_id)
            await callback.message.answer(f"✅ Успешно!\nТвоя ссылка (нажми, чтобы скопировать):\n<code>{link}</code>")
        await state.clear()
    else: await callback.answer("Оплата пока не видна...", show_alert=False)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    if await db.check_trial(callback.from_user.id):
        return await callback.answer("Тест уже был использован!", show_alert=True)
    sub_id = xui.add_client(callback.from_user.id, "Trial", days=2)
    if sub_id:
        await db.add_device(callback.from_user.id, "Trial", sub_id, 2)
        await db.set_trial_used(callback.from_user.id)
        link = os.getenv("VLESS_TEMPLATE").format(sub_id=sub_id)
        await callback.message.answer(f"🎁 Тестовый доступ:\n<code>{link}</code>")
    else: await callback.answer("Ошибка панели")

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    txt = "<b>👤 Твой профиль:</b>\n\n"
    if not devices: txt += "У тебя пока нет активных ключей."
    for d in devices:
        link = os.getenv("VLESS_TEMPLATE").format(sub_id=d['uuid'])
        txt += f"📍 {d['device_name']}:\n<code>{link}</code>\n\n"
    await callback.message.edit_text(txt, reply_markup=main_menu_kb(callback.from_user.id))

@dp.callback_query(F.data == "help")
async def help_info(callback: types.CallbackQuery):
    txt = "<b>📖 Как подключить:</b>\n1. Скопируй ссылку выше.\n2. Открой Streisand.\n3. Нажми + и выбери 'Add Subscription'.\n4. Вставь ссылку."
    await callback.message.edit_text(txt, reply_markup=main_menu_kb(callback.from_user.id))

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
