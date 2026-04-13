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

# Логирование для отслеживания ошибок в консоли
logging.basicConfig(level=logging.INFO)

load_dotenv()

# --- НАСТРОЙКИ ---
ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy" 
CHANNEL_URL = "https://t.me/kent_proxy"
MAX_DEVICES = 5
# Твой базовый URL подписки из настроек панели
BASE_SUB_URL = "https://91.199.32.144:2096/sub"

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

class FormStates(StatesGroup):
    waiting_for_name = State()

# --- ФУНКЦИИ ---

async def check_subscription(user_id):
    """Проверка подписки на канал"""
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

def main_menu_kb(user_id):
    """Главное меню бота"""
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
    
    # Проверка обязательной подписки
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Проверить подписку", callback_data="start_over"))
        txt = "<b>🚫 Доступ ограничен!</b>\n\nПодпишись на наш канал, чтобы получить доступ к приложению."
        if isinstance(event, types.Message): 
            return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    # Приветственный текст БЕЗ названия Кент ВПН
    txt = "<b>🚀 Твой личный обход блокировок!</b>\n\nМаксимальная скорость, стабильность и полная анонимность."
    kb = main_menu_kb(user_id)
    
    if isinstance(event, types.Message): 
        await event.answer(txt, reply_markup=kb)
    else: 
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    """Логика выдачи пробного периода"""
    user_id = callback.from_user.id
    
    if await db.check_trial(user_id):
        return await callback.answer("❌ Тест уже был использован!", show_alert=True)
    
    # Бот стучится в панель
    sub_id = xui.add_client(user_id)
    
    if sub_id:
        await db.add_device(user_id, "Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        
        link = f"{BASE_SUB_URL}/{sub_id}"
        
        await callback.message.answer(
            f"🎁 <b>Бесплатный доступ на 2 дня!</b>\n\n"
            f"Твоя ссылка (нажми, чтобы скопировать):\n"
            f"<code>{link}</code>\n\n"
            f"Инструкции по настройке в разделе '⚙️ Инструкции'.",
            reply_markup=main_menu_kb(user_id)
        )
    else:
        await callback.answer("⚠️ Ошибка панели. Попробуй позже.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    """Просмотр активных ссылок в профиле"""
    devices = await db.get_user_devices(callback.from_user.id)
    
    txt = "<b>👤 Твой профиль</b>\n\n"
    if not devices:
        txt += "У тебя пока нет активных ключей."
    else:
        txt += f"Твои устройства ({len(devices)}/{MAX_DEVICES}):\n\n"
        for d in devices:
            link = f"{BASE_SUB_URL}/{d['uuid']}"
            txt += f"📍 <b>{d['device_name']}</b>\n<code>{link}</code>\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "help")
async def help_info(callback: types.CallbackQuery):
    """Инструкция для пользователей"""
    txt = (
        "<b>⚙️ Как подключиться?</b>\n\n"
        "1. Установи приложение <b>Streisand</b> (iOS) или <b>v2rayNG</b> (Android).\n"
        "2. Скопируй ссылку из профиля или теста.\n"
        "3. В приложении нажми '+' и выбери 'Добавить подписку' или 'Импорт из буфера'.\n"
        "4. Обнови список серверов и нажми кнопку подключения."
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

# --- ЗАПУСК БОТА ---

async def main():
    await db.init_db()
    logging.info("Бот запущен!")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот выключен")
