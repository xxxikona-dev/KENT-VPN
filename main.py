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

# Настройка логирования
logging.basicConfig(level=logging.INFO)

load_dotenv()

# --- КОНФИГУРАЦИЯ ---
ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy" 
CHANNEL_URL = "https://t.me/kent_proxy"
MAX_DEVICES = 5
# Ссылка берется из твоих настроек панели (скриншот с URI обратного прокси)
BASE_SUB_URL = "https://91.199.32.144:2096/sub"

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

class FormStates(StatesGroup):
    waiting_for_name = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def check_subscription(user_id):
    """Проверка подписки (админы всегда проходят)"""
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка подписки: {e}")
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

# --- ХЕНДЛЕРЫ ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    
    # Проверка подписки перед входом
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Проверить", callback_data="start_over"))
        txt = "<b>🚫 Ошибка!</b>\nДля использования бота нужно подписаться на наш канал."
        if isinstance(event, types.Message): 
            return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    txt = "<b>🚀 KENTVPN — Твой личный обход блокировок!</b>"
    kb = main_menu_kb(user_id)
    
    if isinstance(event, types.Message): 
        await event.answer(txt, reply_markup=kb)
    else: 
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    """Выдача теста через 'нажатие кнопки' в панели"""
    user_id = callback.from_user.id
    
    if await db.check_trial(user_id):
        return await callback.answer("❌ Тест уже был использован!", show_alert=True)
    
    # Бот имитирует ручное добавление клиента
    sub_id = xui.add_client(user_id)
    
    if sub_id:
        await db.add_device(user_id, "Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        
        # Выдача HTTPS ссылки как на скрине
        link = f"{BASE_SUB_URL}/{sub_id}"
        
        await callback.message.answer(
            f"🎁 <b>Тестовый доступ готов!</b>\n\n"
            f"Твоя ссылка (HTTPS):\n<code>{link}</code>\n\n"
            f"Настрой её в Streisand или v2rayNG.",
            reply_markup=main_menu_kb(user_id)
        )
    else:
        await callback.answer("Ошибка связи с панелью. Проверь логи.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    """Список всех ключей пользователя"""
    devices = await db.get_user_devices(callback.from_user.id)
    
    txt = "<b>👤 Твой профиль</b>\n\n"
    if not devices:
        txt += "У тебя нет активных подписок."
    else:
        for d in devices:
            link = f"{BASE_SUB_URL}/{d['uuid']}"
            txt += f"📍 <b>{d['device_name']}</b>:\n<code>{link}</code>\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "help")
async def help_info(callback: types.CallbackQuery):
    """Инструкция по подключению"""
    txt = (
        "<b>📖 Как подключить:</b>\n\n"
        "1. Скопируй ссылку из профиля или теста.\n"
        "2. Открой приложение (Streisand, v2rayNG, Nekoray).\n"
        "3. Добавь новую подписку через '+' (Add Subscription).\n"
        "4. Вставь ссылку и нажми 'Обновить'."
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

# --- АДМИН ПАНЕЛЬ ---

@dp.callback_query(F.data == "admin_panel")
async def admin_menu(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    
    # Простая статистика
    users_count = 0 # Тут можно добавить запрос к БД для подсчета
    txt = f"<b>👑 Админ-панель</b>\n\nПользователей в базе: {users_count}"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

# --- ЗАПУСК ---

async def main():
    print("Проверка базы данных...")
    await db.init_db()
    print(f"Бот KENTVPN запущен! Ссылка выдачи: {BASE_SUB_URL}")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
