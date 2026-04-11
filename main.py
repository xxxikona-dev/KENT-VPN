import asyncio
import os
import time
from dotenv import load_dotenv

# Aiogram 3.7.0+ импорты
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Оплата
from yookassa import Configuration, Payment

# Свои модули
import database as db
from xui_api import XUI

# Безопасный импорт CryptoPay
try:
    from aiocryptopay import AioCryptoPay, Networks
    CRYPTOPAY_AVAILABLE = True
except ImportError:
    CRYPTOPAY_AVAILABLE = False
    print("⚠️ aiocryptopay не установлена.")

load_dotenv()

# --- ИСПРАВЛЕННАЯ ИНИЦИАЛИЗАЦИЯ ---
bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
xui = XUI()

# Настройки ЮKassa
Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

# Настройки CryptoPay
crypto = None
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)

class DeviceStates(StatesGroup):
    waiting_for_name = State()

# --- ЛОГИКА БОТА ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_new"))
    builder.row(types.InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_subs"))
    await message.answer("<b>KENTVPN</b> — быстрый и стабильный VPN.\nЦена: 99₽ / 30 дней.", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "my_subs")
async def show_subs(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    if not devices:
        await callback.message.answer("Активных подписок нет.")
        return
    builder = InlineKeyboardBuilder()
    for d in devices:
        builder.row(types.InlineKeyboardButton(text=f"⚙️ {d['device_name']}", callback_data=f"manage_{d['id']}"))
    await callback.message.answer("Ваши устройства:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "buy_new")
async def buy_device(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название устройства (например, iPhone):")
    await state.set_state(DeviceStates.waiting_for_name)

@dp.message(DeviceStates.waiting_for_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(dev_name=message.text)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Картой (RUB)", callback_data="pay_yk"))
    if crypto:
        builder.row(types.InlineKeyboardButton(text="💎 Криптой (USDT)", callback_data="pay_cp"))
    await message.answer(f"Устройство: <b>{message.text}</b>\nВыберите способ оплаты:", reply_markup=builder.as_markup())

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
    builder.row(types.InlineKeyboardButton(text="Оплатить 99₽", url=payment.confirmation.confirmation_url))
    builder.row(types.InlineKeyboardButton(text="✅ Проверить", callback_data=f"check_yk_{payment.id}"))
    await callback.message.answer("Счет в ЮKassa готов:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_yk_"))
async def check_yk(callback: types.CallbackQuery, state: FSMContext):
    pid = callback.data.split("_")[2]
    if Payment.find_one(pid).status == "succeeded":
        data = await state.get_data()
        u_uuid = xui.add_client(callback.from_user.id, data['dev_name'])
        await db.add_device(callback.from_user.id, data['dev_name'], u_uuid)
        link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=data['dev_name'])
        await callback.message.answer(f"✅ Готово!\nКлюч:\n<code>{link}</code>")
        await state.clear()
    else:
        await callback.answer("Оплата не прошла", show_alert=True)

@dp.callback_query(F.data.startswith("manage_"))
async def manage(callback: types.CallbackQuery):
    dev = await db.get_device_by_id(callback.data.split("_")[1])
    days = max(0, (dev['expiry_date'] - time.time()) // 86400)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔑 Ключ", callback_data=f"show_k_{dev['id']}"))
    await callback.message.answer(f"📱 {dev['device_name']}\nОсталось: {int(days)} дн.", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("show_k_"))
async def show_k(callback: types.CallbackQuery):
    dev = await db.get_device_by_id(callback.data.split("_")[2])
    link = os.getenv("VLESS_TEMPLATE").format(uuid=dev['uuid'], device_name=dev['device_name'])
    await callback.message.answer(f"<code>{link}</code>")

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
