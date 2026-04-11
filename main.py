import asyncio
import os
import time
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from yookassa import Configuration, Payment
from aiocryptopay import CryptoPay

import database as db
from xui_api import XUI

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"), parse_mode="HTML")
dp = Dispatcher()
xui = XUI()
crypto = CryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"))

Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

class DeviceStates(StatesGroup):
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_new"))
    builder.row(types.InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_subs"))
    await message.answer("<b>KENTVPN</b> — 99₽/мес. До 5 устройств на ключ.", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "my_subs")
async def show_subs(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    if not devices:
        await callback.message.answer("У вас нет активных подписок.")
        return
    
    builder = InlineKeyboardBuilder()
    for d in devices:
        builder.row(types.InlineKeyboardButton(text=f"⚙️ {d['device_name']}", callback_data=f"manage_{d['id']}"))
    await callback.message.answer("Выберите устройство для управления:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "buy_new")
async def buy_device(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название устройства (например, 'iPhone'):")
    await state.set_state(DeviceStates.waiting_for_name)

@dp.message(DeviceStates.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(dev_name=message.text)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 ЮKassa (RUB)", callback_data="pay_yk"))
    builder.row(types.InlineKeyboardButton(text="💎 CryptoPay (USDT)", callback_data="pay_cp"))
    await message.answer(f"Оплата подписки для <b>{message.text}</b> (99₽)", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_yk")
async def process_yk(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment = Payment.create({
        "amount": {"value": "99.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/your_bot"},
        "capture": True,
        "description": f"VPN: {data['dev_name']}"
    })
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Перейти к оплате", url=payment.confirmation.confirmation_url))
    builder.row(types.InlineKeyboardButton(text="Проверить", callback_data=f"check_{payment.id}"))
    await callback.message.answer("Оплатите счет:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_"))
async def check_pay(callback: types.CallbackQuery, state: FSMContext):
    pid = callback.data.split("_")[1]
    res = Payment.find_one(pid)
    if res.status == "succeeded":
        data = await state.get_data()
        u_uuid = xui.add_client(callback.from_user.id, data['dev_name'])
        await db.add_device(callback.from_user.id, data['dev_name'], u_uuid)
        link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=data['dev_name'])
        await callback.message.answer(f"✅ Готово!\nВаш ключ:\n<code>{link}</code>")
        await state.clear()
    else:
        await callback.answer("Оплата не найдена", show_alert=True)

@dp.callback_query(F.data.startswith("manage_"))
async def manage(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[1]
    dev = await db.get_device_by_id(dev_id)
    days_left = (dev['expiry_date'] - time.time()) // 86400
    text = f"📱 <b>{dev['device_name']}</b>\nОсталось дней: {int(days_left)}"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔄 Продлить (99₽)", callback_data=f"renew_{dev_id}"))
    builder.row(types.InlineKeyboardButton(text="🔑 Показать ключ", callback_data=f"show_{dev_id}"))
    await callback.message.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("show_"))
async def show_key(callback: types.CallbackQuery):
    dev = await db.get_device_by_id(callback.data.split("_")[1])
    link = os.getenv("VLESS_TEMPLATE").format(uuid=dev['uuid'], device_name=dev['device_name'])
    await callback.message.answer(f"Ваш ключ для {dev['device_name']}:\n<code>{link}</code>")

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
