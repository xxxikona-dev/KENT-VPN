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
from aiocryptopay import AioCryptoPay  # ИСПРАВЛЕННЫЙ ИМПОРТ

import database as db
from xui_api import XUI

load_dotenv()

# Инициализация
bot = Bot(token=os.getenv("BOT_TOKEN"), parse_mode="HTML")
dp = Dispatcher()
xui = XUI()
crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN")) # ИСПРАВЛЕННЫЙ КЛАСС

Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

class DeviceStates(StatesGroup):
    waiting_for_name = State()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_new"))
    builder.row(types.InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_subs"))
    await message.answer("<b>KENTVPN</b> — 99₽/мес.\nДо 5 устройств на один ключ.", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "my_subs")
async def show_subs(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    if not devices:
        await callback.message.answer("У вас нет активных подписок.")
        return
    
    builder = InlineKeyboardBuilder()
    for d in devices:
        builder.row(types.InlineKeyboardButton(text=f"⚙️ {d['device_name']}", callback_data=f"manage_{d['id']}"))
    await callback.message.answer("Ваши устройства:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "buy_new")
async def buy_device(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название устройства (например, 'iPhone' или 'My Laptop'):")
    await state.set_state(DeviceStates.waiting_for_name)

@dp.message(DeviceStates.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(dev_name=message.text)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 ЮKassa (RUB)", callback_data="pay_yk"))
    builder.row(types.InlineKeyboardButton(text="💎 CryptoPay (USDT)", callback_data="pay_cp"))
    await message.answer(f"Устройство: <b>{message.text}</b>\nЦена: 99₽\nВыберите способ оплаты:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_yk")
async def process_yk(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment = Payment.create({
        "amount": {"value": "99.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/your_bot_username"},
        "capture": True,
        "description": f"VPN: {data['dev_name']}"
    })
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Оплатить", url=payment.confirmation.confirmation_url))
    builder.row(types.InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_yk_{payment.id}"))
    await callback.message.answer("Оплатите счет через ЮKassa:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_yk_"))
async def check_yk(callback: types.CallbackQuery, state: FSMContext):
    pid = callback.data.split("_")[2]
    res = Payment.find_one(pid)
    if res.status == "succeeded":
        data = await state.get_data()
        u_uuid = xui.add_client(callback.from_user.id, data['dev_name'])
        if u_uuid:
            await db.add_device(callback.from_user.id, data['dev_name'], u_uuid)
            link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=data['dev_name'])
            await callback.message.answer(f"✅ Оплата прошла!\nВаш ключ для <b>{data['dev_name']}</b>:\n<code>{link}</code>")
            await state.clear()
    else:
        await callback.answer("Оплата пока не подтверждена.", show_alert=True)

@dp.callback_query(F.data == "pay_cp")
async def process_cp(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    # Примерная конвертация 99₽ в USDT (около 1.1$)
    invoice = await crypto.create_invoice(asset='USDT', amount=1.1)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Оплатить в CryptoBot", url=invoice.bot_invoice_url))
    builder.row(types.InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_cp_{invoice.invoice_id}"))
    await callback.message.answer("Оплатите счет через CryptoPay:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_cp_"))
async def check_cp(callback: types.CallbackQuery, state: FSMContext):
    iid = int(callback.data.split("_")[2])
    invoices = await crypto.get_invoices(invoice_ids=iid)
    if invoices and invoices.status == 'paid':
        data = await state.get_data()
        u_uuid = xui.add_client(callback.from_user.id, data['dev_name'])
        await db.add_device(callback.from_user.id, data['dev_name'], u_uuid)
        link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=data['dev_name'])
        await callback.message.answer(f"✅ Оплата прошла!\nКлюч для <b>{data['dev_name']}</b>:\n<code>{link}</code>")
        await state.clear()
    else:
        await callback.answer("Счет не оплачен.", show_alert=True)

@dp.callback_query(F.data.startswith("manage_"))
async def manage_dev(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[1]
    dev = await db.get_device_by_id(dev_id)
    days_left = max(0, (dev['expiry_date'] - time.time()) // 86400)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔑 Показать ключ", callback_data=f"show_k_{dev_id}"))
    builder.row(types.InlineKeyboardButton(text="🔄 Продлить (99₽)", callback_data=f"renew_{dev_id}"))
    
    await callback.message.answer(
        f"Устройство: <b>{dev['device_name']}</b>\n"
        f"Статус: {'Активен' if dev['is_active'] else 'Истек'}\n"
        f"Осталось дней: {int(days_left)}",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data.startswith("show_k_"))
async def show_k(callback: types.CallbackQuery):
    dev = await db.get_device_by_id(callback.data.split("_")[2])
    link = os.getenv("VLESS_TEMPLATE").format(uuid=dev['uuid'], device_name=dev['device_name'])
    await callback.message.answer(f"Ваш ключ:\n<code>{link}</code>")

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
