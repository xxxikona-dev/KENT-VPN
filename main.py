import asyncio
import os
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from xui_api import XUI

logging.basicConfig(level=logging.INFO)
load_dotenv()

# --- КОНФИГУРАЦИЯ Happ ---
ADMIN_IDS = [5153650495] 
# ЖЕСТКО ЗАДАЕМ ПОРТ 2096 И ПУТЬ /sub
BASE_SUB_URL = "https://91.199.32.144:2096/sub"

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

def main_menu_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⚡ Подключить Happ Premium", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Попробовать Happ (2 дня)", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Мой доступ", callback_data="profile"),
                types.InlineKeyboardButton(text="📖 Как настроить?", callback_data="help"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Happ Console", callback_data="admin_panel"))
    return builder.as_markup()

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    txt = "<b>Добро пожаловать в Happ! ✨</b>\n\nВыберите действие в меню:"
    kb = main_menu_kb(user_id)
    if isinstance(event, types.Message): await event.answer(txt, reply_markup=kb)
    else:
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in ADMIN_IDS:
        await callback.answer("⭐ Happ Developer Access", show_alert=False)
        sub_id = xui.add_client(user_id, days=365)
        if sub_id:
            await db.add_device(user_id, "Happ VIP", sub_id, 365)
            # Формируем чистую ссылку
            link = f"{BASE_SUB_URL}/{sub_id}"
            return await callback.message.answer(f"✅ <b>VIP доступ готов:</b>\n\n<code>{link}</code>")
        return await callback.answer("Ошибка связи с панелью", show_alert=True)

    txt = "<b>💎 Happ Premium</b>\n\nВыберите тариф..."
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить", callback_data="pay"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS and await db.check_trial(user_id):
        return await callback.answer("❌ Тест уже использован!", show_alert=True)
    
    sub_id = xui.add_client(user_id, days=2)
    if sub_id:
        await db.add_device(user_id, "Happ Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        link = f"{BASE_SUB_URL}/{sub_id}"
        await callback.message.answer(f"🎁 <b>Тест на 2 дня:</b>\n\n<code>{link}</code>")
    else:
        await callback.answer("⚠️ Ошибка сервера", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    txt = "<b>👤 Статус Happ</b>\n\n"
    if not devices: txt += "Нет активных подписок."
    else:
        for d in devices:
            # Важно: берем subId из базы и подставляем в правильный URL
            link = f"{BASE_SUB_URL}/{d['uuid']}"
            txt += f"📍 <code>{link}</code>\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
