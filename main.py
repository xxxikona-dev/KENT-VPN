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

# Интеграция оплаты (CryptoBot)
try:
    from aiocryptopay import AioCryptoPay, Networks
    CRYPTOPAY_AVAILABLE = True
except ImportError:
    CRYPTOPAY_AVAILABLE = False

load_dotenv()

# Настройки проекта
ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy" 
CHANNEL_URL = "https://t.me/kent_proxy"
MAX_DEVICES = 5

# Инициализация бота и API
bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

crypto = None
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)

class FormStates(StatesGroup):
    waiting_for_name = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def check_subscription(user_id):
    """Проверка подписки на канал (админы проходят без проверки)"""
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False

def main_menu_kb(user_id):
    """Главное меню"""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                types.InlineKeyboardButton(text="⚙️ Инструкции", callback_data="help"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel"))
    return builder.as_markup()

# --- ОБРАБОТЧИКИ (HANDLERS) ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    
    # Проверка подписки
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Я подписался", callback_data="start_over"))
        txt = "<b>🚫 Доступ ограничен!</b>\nПодпишитесь на наш канал, чтобы запустить бота."
        if isinstance(event, types.Message): return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    txt = "<b>🚀 KENTVPN — Твой личный обход блокировок!</b>\n\nБыстрые сервера в Великобритании с протоколом Reality."
    kb = main_menu_kb(user_id)
    
    if isinstance(event, types.Message): 
        await event.answer(txt, reply_markup=kb)
    else: 
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    """Выдача тестового периода"""
    user_id = callback.from_user.id
    
    if await db.check_trial(user_id):
        return await callback.answer("❌ Вы уже использовали пробный период!", show_alert=True)
    
    print(f"Попытка выдать тест для {user_id}...")
    sub_id = xui.add_client(user_id, "Trial_Device", days=2)
    
    if sub_id:
        await db.add_device(user_id, "Trial_Device", sub_id, 2)
        await db.set_trial_used(user_id)
        
        # Берем шаблон из .env (там должен быть порт 2096)
        link = os.getenv("VLESS_TEMPLATE").format(sub_id=sub_id)
        
        await callback.message.answer(
            f"🎁 <b>Тестовый доступ на 2 дня готов!</b>\n\n"
            f"Твоя ссылка (нажми, чтобы скопировать):\n"
            f"<code>{link}</code>\n\n"
            f"Инструкция по кнопке ниже 👇", 
            reply_markup=main_menu_kb(user_id)
        )
    else:
        print(f"ОШИБКА: Панель не вернула sub_id для пользователя {user_id}")
        await callback.answer("⚠️ Ошибка связи с сервером. Попробуйте позже.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    """Список устройств пользователя"""
    devices = await db.get_user_devices(callback.from_user.id)
    
    txt = "<b>👤 Твой профиль</b>\n\n"
    if not devices:
        txt += "У тебя пока нет активных ключей."
    else:
        txt += f"Твои устройства ({len(devices)}/{MAX_DEVICES}):\n\n"
        for d in devices:
            # d['uuid'] — это subId, сохраненный в БД при создании
            link = os.getenv("VLESS_TEMPLATE").format(sub_id=d['uuid'])
            txt += f"📍 <b>{d['device_name']}</b>\n<code>{link}</code>\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    """Меню покупки"""
    devices = await db.get_user_devices(callback.from_user.id)
    if len(devices) >= MAX_DEVICES:
        return await callback.answer(f"Максимум {MAX_DEVICES} устройств!", show_alert=True)

    txt = "<b>💎 Premium Подписка (30 дней)</b>\n\n💰 Цена: 1 USDT\n\nПосле оплаты бот создаст для тебя персональную ссылку."
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить 1 USDT", callback_data="pay_crypto"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_crypto")
async def start_pay(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название для нового устройства (например: iPhone 15):")
    await state.set_state(FormStates.waiting_for_name)

@dp.message(FormStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    if not crypto:
        return await message.answer("Ошибка системы оплаты. Напишите админу.")
        
    await state.update_data(dname=message.text)
    invoice = await crypto.create_invoice(asset='USDT', amount=1)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔗 Оплатить через CryptoBot", url=invoice.bot_invoice_url))
    builder.row(types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_{invoice.invoice_id}"))
    
    await message.answer(f"Счет на 1 USDT для устройства <b>{message.text}</b> создан.", reply_markup=builder.as_markup())

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
            await callback.message.answer(f"✅ Оплата принята!\nТвоя ссылка:\n<code>{link}</code>")
            await state.clear()
        else:
            await callback.message.answer("❌ Оплата прошла, но возникла ошибка панели. Напишите @админу!")
    else:
        await callback.answer("Оплата еще не поступила...", show_alert=False)

@dp.callback_query(F.data == "help")
async def help_info(callback: types.CallbackQuery):
    txt = (
        "<b>📖 Как подключить VPN?</b>\n\n"
        "1. Скопируй ссылку из профиля или сообщения.\n"
        "2. Установи приложение <b>Streisand</b> (iOS) или <b>v2rayNG</b> (Android).\n"
        "3. В приложении нажми '+' и выбери <b>'Add Subscription'</b> (или 'Import from Clipboard').\n"
        "4. Вставь ссылку и обнови список серверов.\n"
        "5. Выбери сервер и нажми 'Подключить'."
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

# --- ЗАПУСК ---

async def main():
    print("Инициализация базы данных...")
    await db.init_db()
    print("Бот KENTVPN запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
