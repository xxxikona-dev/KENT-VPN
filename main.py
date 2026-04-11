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

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
xui = XUI()

crypto = None
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)

class DeviceStates(StatesGroup):
    waiting_for_name = State()

# --- КЛАВИАТУРЫ ---

def main_menu_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить VPN (1 USDT)", callback_data="buy_new"))
    builder.row(
        types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton(text="📖 Помощь", callback_data="help")
    )
    builder.row(
        types.InlineKeyboardButton(text="⚙️ Настройка", callback_data="setup"),
        types.InlineKeyboardButton(text="🆘 Поддержка", callback_data="support")
    )
    return builder.as_markup()

def back_to_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ В главное меню", callback_data="start_over"))
    return builder.as_markup()

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "<b>🚀 Добро пожаловать в KENTVPN!</b>\n\n"
        "Мы используем протокол <b>VLESS + Reality</b>, который:\n"
        "✅ Не блокируется провайдерами\n"
        "✅ Работает быстрее обычных VPN\n"
        "✅ Не тратит заряд аккумулятора\n\n"
        "<i>Выберите действие в меню ниже:</i>"
    )
    
    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=main_menu_kb())
    else:
        await event.message.edit_text(text, reply_markup=main_menu_kb())

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    dev_list = ""
    if devices:
        for i, d in enumerate(devices, 1):
            dev_list += f"{i}. <b>{d['device_name']}</b> (Активен)\n"
    else:
        dev_list = "У вас пока нет активных ключей."

    text = (
        "<b>👤 Ваш профиль</b>\n\n"
        f"<b>ID:</b> <code>{callback.from_user.id}</code>\n"
        f"<b>Статус:</b> Пользователь\n\n"
        f"<b>Ваши устройства:</b>\n{dev_list}\n"
        "Чтобы получить ключ повторно, зайдите в раздел 'Настройка'."
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())

@dp.callback_query(F.data == "setup")
async def show_setup(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    if not devices:
        return await callback.answer("У вас нет купленных ключей!", show_alert=True)
    
    builder = InlineKeyboardBuilder()
    for d in devices:
        builder.row(types.InlineKeyboardButton(text=f"🔑 Ключ для {d['device_name']}", callback_data=f"show_k_{d['id']}"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    
    await callback.message.edit_text("Выберите устройство, чтобы получить ключ:", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "help")
async def show_help(callback: types.CallbackQuery):
    text = (
        "<b>📖 Как это работает?</b>\n\n"
        "1. <b>Купите ключ</b> — нажмите кнопку покупки и оплатите счет.\n"
        "2. <b>Скачайте приложение</b> — ссылки в разделе 'Настройка'.\n"
        "3. <b>Скопируйте ключ</b> — он выглядит как длинная ссылка.\n"
        "4. <b>Импорт</b> — вставьте ссылку в приложение и нажмите 'Подключить'.\n\n"
        "Одного ключа достаточно для работы на одном устройстве."
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())

@dp.callback_query(F.data == "support")
async def show_support(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="👨‍💻 Написать админу", url="https://t.me/твой_логин")) # ЗАМЕНИ НА СВОЙ
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    
    await callback.message.edit_text(
        "<b>🆘 Возникли проблемы?</b>\n\n"
        "Если у вас не проходит оплата или не работает ключ, напишите нашей поддержке. "
        "Обязательно приложите ваш ID (указан в профиле).",
        reply_markup=builder.as_markup()
    )

@dp.callback_query(F.data == "buy_new")
async def buy_device(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("🏷 <b>Введите название для вашего устройства:</b>\nНапример: <i>iPhone-Max, My-PC, Android</i>")
    await state.set_state(DeviceStates.waiting_for_name)

@dp.message(DeviceStates.waiting_for_name)
async def get_device_name(message: types.Message, state: FSMContext):
    if not crypto:
        return await message.answer("❌ Оплата USDT сейчас недоступна.")
    
    await state.update_data(dev_name=message.text)
    payment_id = str(uuid.uuid4())
    
    try:
        invoice = await crypto.create_invoice(asset='USDT', amount=1, payload=payment_id)
        pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'pay_url', None)
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="💳 Оплатить в CryptoBot", url=pay_url))
        builder.row(types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_cp_{invoice.invoice_id}_{payment_id}"))
        builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="start_over"))
        
        await message.answer(
            f"<b>Счет на оплату №{invoice.invoice_id}</b>\n\n"
            f"📦 Товар: VPN Подписка (30 дней)\n"
            f"📱 Устройство: <code>{message.text}</code>\n"
            f"💰 Сумма: <b>1 USDT</b>\n\n"
            "После оплаты нажмите кнопку проверки.",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        logging.error(f"Ошибка счета: {e}")
        await message.answer("❌ Ошибка при создании счета. Попробуйте еще раз.")

@dp.callback_query(F.data.startswith("show_k_"))
async def show_key_again(callback: types.CallbackQuery):
    dev_id = callback.data.split("_")[2]
    dev = await db.get_device_by_id(dev_id)
    if dev:
        link = os.getenv("VLESS_TEMPLATE").format(uuid=dev['uuid'], device_name=dev['device_name'])
        await callback.message.answer(f"<b>Ваш ключ:</b>\n\n<code>{link}</code>")
    await callback.answer()

# Остальная логика check_cp_ остается такой же, как в предыдущем сообщении

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
