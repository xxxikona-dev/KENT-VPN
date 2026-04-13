import asyncio
import os
import time
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

# Попытка импорта CryptoPay
try:
    from aiocryptopay import AioCryptoPay, Networks
    CRYPTOPAY_AVAILABLE = True
except ImportError:
    CRYPTOPAY_AVAILABLE = False

load_dotenv()

# --- КОНФИГУРАЦИЯ ---
ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy" 
CHANNEL_URL = "https://t.me/kent_proxy"
MAX_DEVICES = 5
# Твой IP и порт подписки
BASE_SUB_URL = "https://91.199.32.144:2096/sub"

# Инициализация бота
bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

# Инициализация оплаты
crypto = None
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)

class FormStates(StatesGroup):
    waiting_for_name = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def check_subscription(user_id):
    """Проверка подписки на канал (админы игнорируются)"""
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False

def main_menu_kb(user_id):
    """Генерация главного меню"""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                types.InlineKeyboardButton(text="⚙️ Инструкции", callback_data="help"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel"))
    return builder.as_markup()

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Я подписался", callback_data="start_over"))
        txt = "<b>🚫 Доступ ограничен!</b>\nПодпишитесь на наш канал, чтобы использовать бота."
        if isinstance(event, types.Message): return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    txt = "<b>🚀 KENTVPN — Твой личный обход блокировок!</b>\n\nСкорость, стабильность и полная анонимность."
    kb = main_menu_kb(user_id)
    
    if isinstance(event, types.Message): 
        await event.answer(txt, reply_markup=kb)
    else: 
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    """Выдача пробного периода"""
    user_id = callback.from_user.id
    
    if await db.check_trial(user_id):
        return await callback.answer("❌ Тест уже был использован!", show_alert=True)
    
    print(f"Запрос теста для {user_id}...")
    sub_id = xui.add_client(user_id, "Trial", days=2)
    
    if sub_id:
        await db.add_device(user_id, "Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        
        link = f"{BASE_SUB_URL}/{sub_id}"
        
        await callback.message.answer(
            f"🎁 <b>Тестовый доступ на 2 дня!</b>\n\n"
            f"Твоя ссылка (нажми, чтобы скопировать):\n"
            f"<code>{link}</code>\n\n"
            f"Настрой её в приложении по инструкции.", 
            reply_markup=main_menu_kb(user_id)
        )
    else:
        await callback.answer("⚠️ Ошибка связи с панелью. Попробуй позже.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    """Просмотр активных устройств"""
    devices = await db.get_user_devices(callback.from_user.id)
    
    txt = "<b>👤 Твой профиль</b>\n\n"
    if not devices:
        txt += "У тебя пока нет активных подключений."
    else:
        txt += f"Твои устройства ({len(devices)}/{MAX_DEVICES}):\n\n"
        for d in devices:
            link = f"{BASE_SUB_URL}/{d['uuid']}"
            txt += f"📍 <b>{d['device_name']}</b>\n<code>{link}</code>\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    """Меню выбора тарифа"""
    devices = await db.get_user_devices(callback.from_user.id)
    if len(devices) >= MAX_DEVICES:
        return await callback.answer(f"Лимит устройств: {MAX_DEVICES}!", show_alert=True)

    txt = "<b>💎 Premium Подписка (30 дней)</b>\n\n💰 Цена: 1 USDT\n\nБот создаст новую ссылку сразу после оплаты."
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить 1 USDT", callback_data="pay_crypto"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_crypto")
async def start_pay(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название для устройства (например: My Phone):")
    await state.set_state(FormStates.waiting_for_name)

@dp.message(FormStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if not crypto:
        return await message.answer("Система оплаты временно недоступна.")
        
    await state.update_data(dname=message.text)
    invoice = await crypto.create_invoice(asset='USDT', amount=1)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔗 Оплатить", url=invoice.bot_invoice_url))
    builder.row(types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_{invoice.invoice_id}"))
    
    await message.answer(f"Счет на 1 USDT для <b>{message.text}</b>.", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_"))
async def check_p(callback: types.CallbackQuery, state: FSMContext):
    inv_id = int(callback.data.split("_")[1])
    invoices = await crypto.get_invoices(invoice_ids=[inv_id])
    
    if invoices and invoices[0].status == 'paid':
        data = await state.get_data()
        sub_id = xui.add_client(callback.from_user.id, data['dname'], days=30)
        
        if sub_id:
            await db.add_device(callback.from_user.id, data['dname'], sub_id, 30)
            link = f"{BASE_SUB_URL}/{sub_id}"
            await callback.message.answer(f"✅ Оплата прошла!\nТвоя ссылка:\n<code>{link}</code>")
            await state.clear()
        else:
            await callback.message.answer("❌ Ошибка панели. Напиши администратору!")
    else:
        await callback.answer("Оплата не найдена...", show_alert=False)

@dp.callback_query(F.data == "help")
async def help_info(callback: types.CallbackQuery):
    txt = (
        "<b>📖 Инструкция</b>\n\n"
        "1. Скопируй ссылку.\n"
        "2. В приложении (Streisand/v2rayNG) добавь новую подписку.\n"
        "3. Вставь ссылку и нажми 'Обновить'.\n"
        "4. Выбери сервер и подключайся!"
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

# --- ЗАПУСК БОТА ---

async def main():
    print("Инициализация базы данных...")
    await db.init_db()
    print("Бот KENTVPN запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот выключен.")
