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

# Настройка логирования для отладки в терминале
logging.basicConfig(level=logging.INFO)

load_dotenv()

# --- КОНФИГУРАЦИЯ ---
ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy" 
CHANNEL_URL = "https://t.me/kent_proxy"
MAX_DEVICES = 5
# Базовая ссылка на подписку (из твоего URI обратного прокси)
BASE_SUB_URL = "https://91.199.32.144:2096/sub"

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

class FormStates(StatesGroup):
    waiting_for_name = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def check_subscription(user_id):
    """Проверка, подписан ли пользователь на канал"""
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

def main_menu_kb(user_id):
    """Генерация клавиатуры главного меню"""
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
    
    # Проверка подписки перед использованием
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Я подписался", callback_data="start_over"))
        txt = "<b>🚫 Доступ ограничен!</b>\n\nЧтобы пользоваться ботом, нужно быть подписанным на наш канал."
        if isinstance(event, types.Message): 
            return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    # Текст приветствия (уже без названия проекта в начале)
    txt = "<b>🚀 Твой личный обход блокировок!</b>\n\nВыбирай нужный раздел ниже:"
    kb = main_menu_kb(user_id)
    
    if isinstance(event, types.Message): 
        await event.answer(txt, reply_markup=kb)
    else: 
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    """Выдача теста строго на 2 дня"""
    user_id = callback.from_user.id
    
    if await db.check_trial(user_id):
        return await callback.answer("❌ Ты уже брал тестовый период!", show_alert=True)
    
    # ПЕРЕДАЕМ 2 ДНЯ В API
    sub_id = xui.add_client(user_id, days=2)
    
    if sub_id:
        # Сохраняем информацию в локальную базу бота
        await db.add_device(user_id, "Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        
        link = f"{BASE_SUB_URL}/{sub_id}"
        
        await callback.message.answer(
            f"🎁 <b>Тестовый доступ на 48 часов готов!</b>\n\n"
            f"Твоя ссылка (нажми, чтобы скопировать):\n"
            f"<code>{link}</code>\n\n"
            f"Сервер: <b>[UK] Великобритания</b>",
            reply_markup=main_menu_kb(user_id)
        )
    else:
        await callback.answer("⚠️ Ошибка на стороне сервера. Попробуй позже.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    """Раздел профиля со всеми ключами"""
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
    """Инструкция по настройке"""
    txt = (
        "<b>⚙️ Быстрая настройка:</b>\n\n"
        "1. Установи <b>Streisand</b> из App Store.\n"
        "2. Скопируй свою ссылку из профиля.\n"
        "3. В приложении нажми ➕ и выбери импорт из буфера.\n"
        "4. Обнови подписку и включи VPN."
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

async def main():
    await db.init_db()
    logging.info("--- БОТ ЗАПУЩЕН ---")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
