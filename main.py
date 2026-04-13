import asyncio
import os
import logging
import uuid
import re
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiocryptopay import AioCryptoPay, Networks

import database as db
from xui_api import XUI

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO)
load_dotenv()

# --- КОНФИГУРАЦИЯ ---
ADMIN_IDS = [5153650495]
CHANNEL_ID = "@kent_proxy"
CHANNEL_URL = "https://t.me/kent_proxy"
BASE_SUB_URL = "https://91.199.32.144:2096/sub"
PRICE_USDT = 1.0

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

# Инициализация Crypto Pay
crypto = AioCryptoPay(token=os.getenv("CRYPTOBOT_TOKEN"), network=Networks.MAIN_NET)

# --- ФУНКЦИИ ПРОВЕРКИ ---

async def check_subscription(user_id: int):
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

def main_menu_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text=f"💎 Купить подписку ({PRICE_USDT} USDT)", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
                types.InlineKeyboardButton(text="⚙️ Инструкция (Happ)", callback_data="help"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    
    # Регистрация в БД
    await db.add_user_to_db(user_id, event.from_user.username)

    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Я подписался", callback_data="start_over"))
        txt = "<b>🚫 Доступ ограничен!</b>\n\nПодпишись на <b>KENT-VPN</b>, чтобы пользоваться ботом."
        if isinstance(event, types.Message): return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    txt = "<b>🚀 KENT-VPN — Твой быстрый доступ к сети!</b>\n\nВыбирай нужный раздел в меню ниже:"
    kb = main_menu_kb(user_id)
    if isinstance(event, types.Message): await event.answer(txt, reply_markup=kb)
    else:
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

# --- ЛОГИКА ОПЛАТЫ ---

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # Админ-выдача (бесплатно)
    if user_id in ADMIN_IDS:
        await callback.answer("👑 Привет, Админ! Ключ на год создан.")
        sub_id = xui.add_client(user_id, days=365)
        if sub_id:
            await db.add_device(user_id, "KENT VIP (Admin)", sub_id, 365)
            return await callback.message.answer(f"✅ <b>VIP готов:</b> <code>{BASE_SUB_URL}/{sub_id}</code>")

    try:
        # Создаем платеж
        payment_id = str(uuid.uuid4())
        invoice = await crypto.create_invoice(asset='USDT', amount=PRICE_USDT, payload=payment_id)
        
        # Получаем URL (учитываем разные версии API)
        pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'pay_url', None)

        txt = (
            f"<b>💎 Подписка KENT-VPN Premium</b>\n\n"
            f"📍 Срок: <b>30 дней</b>\n"
            f"💰 Цена: <b>{PRICE_USDT} USDT</b>\n\n"
            f"<i>Оплатите счет и нажмите кнопку подтверждения.</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="💳 Оплатить через CryptoBot", url=pay_url))
        builder.row(types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"checkpay:{invoice.invoice_id}"))
        builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
        
        await callback.message.edit_text(txt, reply_markup=builder.as_markup())
    except Exception as e:
        logging.error(f"Ошибка создания счета: {e}")
        await callback.answer("❌ Ошибка платежной системы", show_alert=True)

@dp.callback_query(F.data.startswith("checkpay:"))
async def check_pay_status(callback: types.CallbackQuery):
    invoice_id = int(callback.data.split(":")[1])
    
    try:
        invoices = await crypto.get_invoices(invoice_ids=[invoice_id])
        invoice = invoices[0] if invoices else None

        if invoice and invoice.status == 'paid':
            user_id = callback.from_user.id
            sub_id = xui.add_client(user_id, days=30)
            if sub_id:
                await db.add_device(user_id, "KENT Premium", sub_id, 30)
                link = f"{BASE_SUB_URL}/{sub_id}"
                await callback.message.answer(f"🚀 <b>Оплата прошла!</b>\n\nТвоя ссылка на 30 дней:\n<code>{link}</code>\n\nИспользуй приложение <b>Happ</b>.")
                await callback.message.delete()
            else:
                await callback.answer("❌ Ошибка создания ключа. Пиши админу!", show_alert=True)
        else:
            await callback.answer("⚠️ Оплата еще не найдена.", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка проверки оплаты: {e}")
        await callback.answer("❌ Ошибка при проверке платежа.", show_alert=True)

# --- ТЕСТОВЫЙ ПЕРИОД И ПРОФИЛЬ ---

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS and await db.check_trial(user_id):
        return await callback.answer("❌ Тестовый период уже использован!", show_alert=True)
    
    sub_id = xui.add_client(user_id, days=2)
    if sub_id:
        await db.add_device(user_id, "KENT Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        await callback.message.answer(f"🎁 <b>Тест на 2 дня готов:</b>\n\n<code>{BASE_SUB_URL}/{sub_id}</code>")
    else:
        await callback.answer("⚠️ Сервер занят, попробуй позже.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    txt = "<b>👤 Мой KENT-VPN</b>\n\n"
    if not devices:
        txt += "У тебя пока нет активных подписок."
    else:
        for d in devices:
            link = f"{BASE_SUB_URL}/{d['uuid']}"
            txt += f"📍 <b>{d['device_name']}</b>:\n<code>{link}</code>\n\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "help")
async def show_help(callback: types.CallbackQuery):
    txt = (
        "<b>⚙️ Инструкция для приложения Happ:</b>\n\n"
        "1. Скачай <b>Happ</b> из App Store.\n"
        "2. Скопируй ссылку из бота.\n"
        "3. Открой Happ и нажми на <b>'+'</b> (Add Subscription).\n"
        "4. Вставь ссылку и подключайся!"
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
