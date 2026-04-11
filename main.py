import asyncio
import os
import time
import uuid
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

# --- КОНФИГ ---
ADMIN_IDS = [5153650495] # Твой ID прописан для админки

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
xui = XUI()

crypto = None
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)

class FormStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_admin_id = State()

# --- КЛАВИАТУРЫ ---

def main_menu_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(
        types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        types.InlineKeyboardButton(text="⚙️ Инструкции", callback_data="help")
    )
    builder.row(types.InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"))
    
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    
    return builder.as_markup()

def back_to_main_kb():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ В главное меню", callback_data="start_over"))
    return builder.as_markup()

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "<b>🚀 KENTVPN — Твой личный доступ без границ!</b>\n\n"
        "Мы используем протокол <b>VLESS + Reality</b>. Это значит:\n"
        "• Трафик выглядит как обычный просмотр сайта\n"
        "• Высокая скорость и низкий пинг\n"
        "• Работает даже при сильных блокировках\n\n"
        "<i>Выберите действие в меню:</i>"
    )
    kb = main_menu_kb(event.from_user.id)
    
    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=kb)
    else:
        await event.message.edit_text(text, reply_markup=kb)

# --- РАЗДЕЛ ПОКУПКИ ---
@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    text = (
        "<b>💎 KENTVPN Premium (30 дней)</b>\n\n"
        "✅ Доступ ко всем заблокированным ресурсам\n"
        "✅ Высокая скорость (до 1 Гбит/с)\n"
        "✅ Поддержка iOS, Android, Windows, macOS\n"
        "✅ Без ограничений по объему трафика\n\n"
        "💰 <b>Цена: 1 USDT</b>\n\n"
        "<i>Для продолжения нажмите кнопку оплаты:</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить через CryptoBot", callback_data="pay_crypto"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_crypto")
async def start_crypto_pay(callback: types.CallbackQuery, state: FSMContext):
    if not crypto: 
        return await callback.answer("❌ Оплата временно недоступна", show_alert=True)
    
    await callback.message.answer("🏷 Введите имя устройства (например: iPhone, Android, PC):")
    await state.set_state(FormStates.waiting_for_name)

@dp.message(FormStates.waiting_for_name)
async def create_invoice(message: types.Message, state: FSMContext):
    dev_name = message.text
    await state.update_data(dname=dev_name)
    
    payment_id = str(uuid.uuid4())
    try:
        invoice = await crypto.create_invoice(asset='USDT', amount=1, payload=payment_id)
        pay_url = getattr(invoice, 'bot_invoice_url', None) or getattr(invoice, 'pay_url', None)
        
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="🔗 Перейти к оплате", url=pay_url))
        builder.row(types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_{invoice.invoice_id}_{payment_id}"))
        builder.row(types.InlineKeyboardButton(text="❌ Отмена", callback_data="start_over"))
        
        await message.answer(
            f"<b>Счет на оплату подписки</b>\n\n"
            f"📦 Товар: VPN (30 дней)\n"
            f"📱 Устройство: <code>{dev_name}</code>\n"
            f"💰 Сумма: <b>1 USDT</b>\n\n"
            "После оплаты в CryptoBot обязательно нажмите кнопку ниже:",
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        await message.answer("❌ Ошибка при создании счета. Попробуйте позже.")

@dp.callback_query(F.data.startswith("check_"))
async def check_payment_status(callback: types.CallbackQuery, state: FSMContext):
    inv_id = int(callback.data.split("_")[1])
    invoices = await crypto.get_invoices(invoice_ids=[inv_id])
    
    if invoices and invoices[0].status == 'paid':
        sdata = await state.get_data()
        dname = sdata.get('dname', 'Device')
        
        u_uuid = xui.add_client(callback.from_user.id, dname)
        if u_uuid:
            await db.add_device(callback.from_user.id, dname, u_uuid, expiry_days=30)
            link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=dname)
            await callback.message.answer(
                f"✅ <b>Оплата принята! Подписка активирована.</b>\n\nВаш ключ:\n<code>{link}</code>",
                reply_markup=back_to_main_kb()
            )
            await state.clear()
        else:
            await callback.answer("Ошибка при создании ключа на сервере.", show_alert=True)
    else:
        await callback.answer("⏳ Оплата еще не получена. Подождите немного и попробуйте снова.", show_alert=True)

# --- ЛОГИКА ТРИАЛА ---
@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await db.check_trial(user_id):
        return await callback.answer("❌ Вы уже использовали пробный период!", show_alert=True)
    
    dev_name = f"Trial_{user_id}"
    u_uuid = xui.add_client(user_id, dev_name)
    
    if u_uuid:
        await db.add_device(user_id, dev_name, u_uuid, expiry_days=2)
        await db.set_trial_used(user_id)
        link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name=dev_name)
        await callback.message.answer(
            f"🎁 <b>Вам начислено 2 дня тестового периода!</b>\n\nКлюч:\n<code>{link}</code>",
            reply_markup=back_to_main_kb()
        )
    else:
        await callback.answer("Ошибка связи с сервером.", show_alert=True)

# --- АДМИН ПАНЕЛЬ ---
@dp.callback_query(F.data == "admin_panel")
async def admin_main(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="➕ Выдать VPN (Бесплатно)", callback_data="admin_give"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text("<b>👑 Панель управления</b>", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_give")
async def admin_give_id(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите Telegram ID пользователя, которому выдать доступ:")
    await state.set_state(FormStates.waiting_for_admin_id)

@dp.message(FormStates.waiting_for_admin_id)
async def admin_give_finish(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS: return
    try:
        target_id = int(message.text)
        u_uuid = xui.add_client(target_id, "Admin_Gift")
        if u_uuid:
            await db.add_device(target_id, "Admin_Gift", u_uuid, expiry_days=365) # на год
            link = os.getenv("VLESS_TEMPLATE").format(uuid=u_uuid, device_name="Admin_Gift")
            await message.answer(f"✅ Успешно! Выдано юзеру {target_id}")
            try:
                await bot.send_message(target_id, f"🎁 Администратор выдал вам бесплатную подписку!\n\nКлюч:\n<code>{link}</code>")
            except: pass
        else:
            await message.answer("Ошибка в панели 3X-UI.")
    except:
        await message.answer("Ошибка. Введите числовой ID.")
    await state.clear()

# --- ВСПОМОГАТЕЛЬНЫЕ РАЗДЕЛЫ ---
@dp.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    text = f"<b>👤 Профиль</b>\nID: <code>{callback.from_user.id}</code>\n\n<b>Ваши активные ключи:</b>\n"
    if not devices:
        text += "У вас пока нет купленных подписок."
    else:
        for i, d in enumerate(devices, 1):
            link = os.getenv("VLESS_TEMPLATE").format(uuid=d['uuid'], device_name=d['device_name'])
            text += f"{i}. <b>{d['device_name']}</b>: <code>{link}</code>\n"
    
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())

@dp.callback_query(F.data == "help")
async def show_help(callback: types.CallbackQuery):
    text = (
        "<b>⚙️ Инструкция по настройке:</b>\n\n"
        "1. Скачайте приложение:\n"
        "— iOS: <b>Streisand</b> или <b>V2Box</b>\n"
        "— Android: <b>v2rayNG</b>\n"
        "— PC: <b>Nekobox</b>\n\n"
        "2. Скопируйте ваш ключ из раздела 'Профиль'.\n"
        "3. В приложении нажмите кнопку '+' (Добавить) -> Import from Clipboard.\n"
        "4. Выберите добавленный сервер и нажмите Connect."
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_kb())

@dp.callback_query(F.data == "support")
async def show_support(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "<b>🆘 Техническая поддержка</b>\n\nПо всем вопросам пишите: @твой_логин",
        reply_markup=back_to_main_kb()
    )

async def main():
    await db.init_db()
    print("🚀 Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
