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

# --- КОНФИГУРАЦИЯ KENT-VPN ---
ADMIN_IDS = [5153650495]
CHANNEL_ID = "@kent_proxy"
CHANNEL_URL = "https://t.me/kent_proxy"
BASE_SUB_URL = "https://91.199.32.144:2096/sub"

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

def main_menu_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку KENT", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
                types.InlineKeyboardButton(text="⚙️ Инструкция (Happ)", callback_data="help"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()

async def check_subscription(user_id: int):
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Я подписался", callback_data="start_over"))
        txt = "<b>🚫 Доступ ограничен!</b>\n\nПодпишись на канал <b>KENT-VPN</b>, чтобы продолжить."
        if isinstance(event, types.Message): return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    txt = "<b>🚀 KENT-VPN — Твой быстрый доступ к сети!</b>\n\nВыбирай нужный раздел в меню ниже:"
    kb = main_menu_kb(user_id)
    if isinstance(event, types.Message): await event.answer(txt, reply_markup=kb)
    else:
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # --- АДМИН-ЧИТ ДЛЯ ТЕБЯ ---
    if user_id in ADMIN_IDS:
        await callback.answer("👑 Привет, Админ! Выдаю ключ на 365 дней...", show_alert=False)
        sub_id = xui.add_client(user_id, days=365)
        if sub_id:
            await db.add_device(user_id, "KENT VIP (Admin)", sub_id, 365)
            link = f"{BASE_SUB_URL}/{sub_id}"
            return await callback.message.answer(f"✅ <b>Твой VIP доступ готов:</b>\n\n<code>{link}</code>")
        return await callback.answer(" Ошибка связи с панелью", show_alert=True)

    txt = "<b>💎 Подписка KENT-VPN Premium</b>\n\n💰 30 дней — 300₽\n\n<i>Мгновенная выдача ключа после оплаты.</i>"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Перейти к оплате", callback_data="pay_process"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS and await db.check_trial(user_id):
        return await callback.answer("❌ Тестовый период уже использован!", show_alert=True)
    
    sub_id = xui.add_client(user_id, days=2)
    if sub_id:
        await db.add_device(user_id, "KENT Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        link = f"{BASE_SUB_URL}/{sub_id}"
        await callback.message.answer(f"🎁 <b>Тест на 2 дня активирован!</b>\n\n<code>{link}</code>\n\nИспользуй приложение <b>Happ</b> для подключения.")
    else:
        await callback.answer("⚠️ Ошибка сервера. Попробуй позже.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    txt = "<b>👤 Мой KENT-VPN</b>\n\n"
    if not devices: txt += "Активных подписок не найдено."
    else:
        for d in devices:
            link = f"{BASE_SUB_URL}/{d['uuid']}"
            txt += f"📍 <b>{d['device_name']}</b>:\n<code>{link}</code>\n\n"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "help")
async def help_info(callback: types.CallbackQuery):
    txt = (
        "<b>⚙️ Инструкция по настройке через Happ:</b>\n\n"
        "1. Скачай приложение <b>Happ</b> из App Store.\n"
        "2. Скопируй свою ссылку KENT-VPN из профиля.\n"
        "3. В приложении Happ нажми кнопку импорта (значок '+').\n"
        "4. Выбери сервер и нажми кнопку подключения."
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

async def main():
    await db.init_db()
    logging.info("KENT-VPN Bot Started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
