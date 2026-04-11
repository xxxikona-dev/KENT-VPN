import asyncio
import os
import time
from dotenv import load_dotenv

# Импорты aiogram с учетом версии 3.7.0+
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
    print("⚠️ aiocryptopay не установлена. Крипто-платежи отключены.")

load_dotenv()

# --- ИНИЦИАЛИЗАЦИЯ БОТА (Исправлено под 3.7.0+) ---
bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
xui = XUI()

# Настройка ЮKassa
Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")

# Настройка CryptoPay
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)
else:
    crypto = None

class DeviceStates(StatesGroup):
    waiting_for_name = State()

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку (99₽)", callback_data="buy_new"))
    builder.row(types.InlineKeyboardButton(text="📱 Мои устройства", callback_data="my_subs"))
    
    await message.answer(
        "<b>Добро пожаловать в KENTVPN!</b>\n\n"
        "• Цена: 99₽ за 30 дней\n"
        "• Лимит: до 5 устройств на ключ\n"
        "• Протокол: VLESS + Reality",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "my_subs")
async def show_subs(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    if not devices:
        await callback.message.answer("У вас пока нет активных устройств.")
        return
    
    builder = InlineKeyboardBuilder()
    for d in devices:
        builder.row(types.InlineKeyboardButton(text=f"⚙️ {d['device_name']}", callback_data=f"manage_{d['id']}"))
    
    await callback.message.answer("Ваши устройства:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "buy_new")
async def buy_device(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название устройства (например, 'iPhone' или 'PC'):")
    await state.set_state(DeviceStates.waiting_for_name)

@dp.message(DeviceStates.waiting_for_name)
async def get_device_name(message: types.Message, state: FSMContext):
    await state.update_data(dev_name=message.text)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 ЮKassa (Карты)", callback_data="pay_yk"))
    if CRYPTOPAY_AVAILABLE:
        builder.row(types.InlineKeyboardButton(text="💎 CryptoPay", callback_data="pay_cp"))
    
    await message.answer(f"Устройство: <b>{message.text}</b>\nЦена: 99₽\nВыберите способ оплаты:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_yk")
async def process_yk(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    payment = Payment.create({
        "amount": {"value": "99.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": "https://t.me/your_bot_user"},
        "capture": True,
        "description": f"VPN: {data['dev_name']}"
    })
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="Оплатить", url=payment.confirmation.confirmation_url))
    builder.row(types.InlineKeyboardButton(text="✅ Проверить", callback_data=f"check_yk_{payment.id}"))
    await callback.message.answer("Счет в ЮKassa:", reply_markup=builder.as_markup())

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
            await callback.message.answer(f"✅ Готово!\n\nКлюч:\n<code>{link}</code>")
            await state.clear()
    else:
        await callback.answer("Оплата не найдена.", show_alert=True)

@dp.callback_query(F.data.startswith("manage_"))
async def manage(callback: types.CallbackQuery):
    dev = await db.get_device_by_id(callback.data.split("_")[1])
    days_left = max(0, (dev['expiry_date'] - time.time()) // 86400)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔑 Ключ", callback_data=f"show_k_{dev['id']}"))
    await callback.message.answer(f"📱 {dev['device_name']}\nОсталось: {int(days_left)} дн.", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("show_k_"))
async def show_k(callback: types.CallbackQuery):
    dev = await db.get_device_by_id(callback.data.split("_")[2])
    link = os.getenv("VLESS_TEMPLATE").format(uuid=dev['uuid'], device_name=dev['device_name'])
    await callback.message.answer(f"Ключ:\n<code>{link}</code>")

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
