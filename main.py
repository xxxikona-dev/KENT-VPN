import asyncio
import os
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiocryptopay import CryptoPay # Импортируем платежку

import database as db
from xui_api import XUI

logging.basicConfig(level=logging.INFO)
load_dotenv()

# --- КОНФИГУРАЦИЯ ---
ADMIN_IDS = [5153650495]
CHANNEL_ID = "@kent_proxy"
CHANNEL_URL = "https://t.me/kent_proxy"
BASE_SUB_URL = "https://91.199.32.144:2096/sub"

# Инициализация
bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

# Настройка Crypto Pay (Добавь CRYPTO_PAY_TOKEN в .env)
crypto = CryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network='mainnet')

def main_menu_kb(user_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку (1 USDT)", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile"),
                types.InlineKeyboardButton(text="⚙️ Инструкция (Happ)", callback_data="help"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    txt = "<b>🚀 KENT-VPN — Доступ в одно касание!</b>\n\nВыбирай нужный раздел:"
    kb = main_menu_kb(user_id)
    if isinstance(event, types.Message): await event.answer(txt, reply_markup=kb)
    else:
        try: await event.message.edit_text(txt, reply_markup=kb)
        except: await event.message.answer(txt, reply_markup=kb)

# --- ЛОГИКА ОПЛАТЫ И ВЫДАЧИ ---

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # Админ-чит (бесплатно)
    if user_id in ADMIN_IDS:
        sub_id = xui.add_client(user_id, days=365)
        if sub_id:
            await db.add_device(user_id, "KENT VIP (Admin)", sub_id, 365)
            return await callback.message.answer(f"✅ <b>VIP готов:</b> <code>{BASE_SUB_URL}/{sub_id}</code>")

    # Создаем счет на 1 USDT
    invoice = await crypto.create_invoice(asset='USDT', amount=1)
    
    txt = (
        "<b>💎 Подписка KENT-VPN Premium</b>\n\n"
        "📍 Срок: 30 дней\n"
        "💰 Цена: <b>1 USDT</b>\n\n"
        "После оплаты подписка появится автоматически."
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить 1 USDT", url=invoice.pay_url))
    # Кнопка для проверки оплаты
    builder.row(types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_{invoice.invoice_id}"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_"))
async def check_pay(callback: types.CallbackQuery):
    invoice_id = int(callback.data.split("_")[1])
    invoices = await crypto.get_invoices(invoice_ids=invoice_id)
    
    if invoices and invoices.status == 'paid':
        user_id = callback.from_user.id
        await callback.message.edit_text("⏳ Оплата подтверждена! Создаю ключ...")
        
        sub_id = xui.add_client(user_id, days=30)
        if sub_id:
            await db.add_device(user_id, "KENT Premium", sub_id, 30)
            link = f"{BASE_SUB_URL}/{sub_id}"
            await callback.message.answer(f"🚀 <b>Оплата прошла! Твоя подписка на 30 дней:</b>\n\n<code>{link}</code>")
        else:
            await callback.message.answer("❌ Ошибка API. Напишите админу!")
    else:
        await callback.answer("⚠️ Оплата еще не поступила", show_alert=True)

# --- ОСТАЛЬНЫЕ ФУНКЦИИ (ТРИАЛ, ПРОФИЛЬ) ---
# (Оставь их такими же, как в твоем коде)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in ADMIN_IDS and await db.check_trial(user_id):
        return await callback.answer("❌ Тест уже был использован!", show_alert=True)
    
    sub_id = xui.add_client(user_id, days=2)
    if sub_id:
        await db.add_device(user_id, "KENT Trial", sub_id, 2)
        await db.set_trial_used(user_id)
        await callback.message.answer(f"🎁 <b>Тест на 2 дня:</b>\n<code>{BASE_SUB_URL}/{sub_id}</code>")
    else:
        await callback.answer("⚠️ Ошибка сервера", show_alert=True)

async def main():
    await db.init_db()
    logging.info("KENT-VPN Bot with CryptoPay Started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
