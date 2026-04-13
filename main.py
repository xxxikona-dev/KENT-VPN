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

# --- ТВОИ ДАННЫЕ ---
ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy"
# Ссылка подписки (используем домен/IP из .env)
BASE_SUB_URL = f"{os.getenv('PANEL_URL')}/sub"

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

def main_menu_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                types.InlineKeyboardButton(text="⚙️ Инструкции", callback_data="help"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel"))
    return builder.as_markup()

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    txt = "<b>🚀 Система готова!</b>\n\nВыбирай нужный раздел в меню:"
    kb = main_menu_kb(user_id)
    if isinstance(event, types.Message): await event.answer(txt, reply_markup=kb)
    else:
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # АДМИН-ЧИТ: если нажал ты — подписка выдается сразу на год
    if user_id in ADMIN_IDS:
        await callback.answer("👑 Доступ для разработчика разрешен!", show_alert=False)
        sub_id = xui.add_client(user_id, days=365)
        if sub_id:
            await db.add_device(user_id, "Admin VIP", sub_id, 365)
            return await callback.message.answer(f"✅ <b>Твой VIP ключ:</b>\n<code>{BASE_SUB_URL}/{sub_id}</code>")
        return await callback.answer("❌ Ошибка API панели", show_alert=True)

    # Обычное меню для юзеров
    txt = "<b>💎 Платная подписка:</b>\n\n💰 30 дней — 300₽\n💰 90 дней — 800₽\n\n<i>Для покупки напишите @админ (или выбери способ оплаты ниже)</i>"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить (Demo)", callback_data="pay_demo"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    # Админу тест выдаем всегда
    if user_id not in ADMIN_IDS and await db.check_trial(user_id):
        return await callback.answer("❌ Вы уже использовали тест!", show_alert=True)
    
    sub_id = xui.add_client(user_id, days=2)
    if sub_id:
        await db.add_device(user_id, "Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        await callback.message.answer(f"🎁 <b>Ссылка на 48 часов:</b>\n<code>{BASE_SUB_URL}/{sub_id}</code>")
    else:
        await callback.answer("⚠️ Ошибка сервера панели", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    txt = "<b>👤 Профиль</b>\n\n"
    if not devices:
        txt += "У вас нет активных подписок."
    else:
        for d in devices:
            txt += f"📍 Ссылка:\n<code>{BASE_SUB_URL}/{d['uuid']}</code>\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

async def main():
    await db.init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
