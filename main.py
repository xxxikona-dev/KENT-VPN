import asyncio
import os
import time
import uuid
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

# Пытаемся импортировать оплату
try:
    from aiocryptopay import AioCryptoPay, Networks
    CRYPTOPAY_AVAILABLE = True
except ImportError:
    CRYPTOPAY_AVAILABLE = False

load_dotenv()

# Глобальные переменные проекта
ADMIN_IDS = [5153650495] 
CHANNEL_ID = "@kent_proxy" 
CHANNEL_URL = "https://t.me/kent_proxy"
MAX_DEVICES = 5

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
xui = XUI()

crypto = None
if CRYPTOPAY_AVAILABLE and os.getenv("CRYPTO_PAY_TOKEN"):
    crypto = AioCryptoPay(token=os.getenv("CRYPTO_PAY_TOKEN"), network=Networks.MAIN_NET)

class FormStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_admin_id = State()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

async def check_subscription(user_id):
    if user_id in ADMIN_IDS: return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except: return False

def main_menu_kb(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                types.InlineKeyboardButton(text="⚙️ Инструкции", callback_data="help"))
    builder.row(types.InlineKeyboardButton(text="🆘 Поддержка", callback_data="support"))
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админ-панель", callback_data="admin_panel"))
    return builder.as_markup()

# --- ОБРАБОТЧИКИ (HANDLERS) ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    user_id = event.from_user.id
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Проверить", callback_data="start_over"))
        txt = "<b>🚫 Доступ ограничен!</b>\nПодпишитесь на канал, чтобы пользоваться ботом."
        if isinstance(event, types.Message): 
            return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    txt = "<b>🚀 KENTVPN — Твой доступ без границ!</b>"
    kb = main_menu_kb(user_id)
    if isinstance(event, types.Message): 
        await event.answer(txt, reply_markup=kb)
    else: 
        await event.message.edit_text(txt, reply_markup=kb)

@dp.callback_query(F.data == "buy_menu")
async def buy_menu(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    if len(devices) >= MAX_DEVICES and callback.from_user.id not in ADMIN_IDS:
        return await callback.answer(f"Лимит {MAX_DEVICES} устройств исчерпан!", show_alert=True)
    
    txt = "<b>💎 Premium VPN (30 дней)</b>\n\n💰 Цена: 1 USDT\n⚠️ Лимит: до 5 устройств."
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💳 Оплатить", callback_data="pay_crypto"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "pay_crypto")
async def start_pay(callback: types.CallbackQuery, state: FSMContext):
    # Если админ, выдаем сразу
    if callback.from_user.id in ADMIN_IDS:
        print(f"Выдача админского ключа для {callback.from_user.id}")
        sub_id = xui.add_client(callback.from_user.id, "Admin_Key", days=365)
        if sub_id:
            await db.add_device(callback.from_user.id, "Admin_Key", sub_id, 365)
            link = os.getenv("VLESS_TEMPLATE").format(sub_id=sub_id)
            return await callback.message.answer(f"👑 <b>Ключ для админа:</b>\n<code>{link}</code>")
        else:
            return await callback.answer("Ошибка создания ключа", show_alert=True)
    
    await callback.message.answer("Введите название устройства (например, iPhone):")
    await state.set_state(FormStates.waiting_for_name)

@dp.message(FormStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(dname=message.text)
    invoice = await crypto.create_invoice(asset='USDT', amount=1)
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔗 Оплатить", url=invoice.bot_invoice_url))
    builder.row(types.InlineKeyboardButton(text="✅ Проверить оплату", callback_data=f"check_{invoice.invoice_id}"))
    await message.answer(f"💰 Счет на 1 USDT создан для устройства: {message.text}\n\nПосле оплаты нажмите «Проверить оплату»", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("check_"))
async def check_payment(callback: types.CallbackQuery, state: FSMContext):
    inv_id = int(callback.data.split("_")[1])
    invoices = await crypto.get_invoices(invoice_ids=[inv_id])
    if invoices and invoices[0].status == 'paid':
        data = await state.get_data()
        device_name = data.get('dname', 'Device')
        sub_id = xui.add_client(callback.from_user.id, device_name, days=30)
        if sub_id:
            await db.add_device(callback.from_user.id, device_name, sub_id, 30)
            link = os.getenv("VLESS_TEMPLATE").format(sub_id=sub_id)
            await callback.message.answer(f"✅ Оплата прошла успешно!\n\n🔗 Ваша подписка:\n<code>{link}</code>\n\n📱 Устройство: {device_name}")
            await callback.message.answer("Главное меню:", reply_markup=main_menu_kb(callback.from_user.id))
        else:
            await callback.answer("Ошибка создания ключа, обратитесь к администратору", show_alert=True)
        await state.clear()
    else:
        await callback.answer("⏳ Оплата еще не найдена. Оплатите счет и нажмите кнопку снова", show_alert=True)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    # Проверял ли уже пробный период
    if await db.check_trial(callback.from_user.id):
        return await callback.answer("❌ Вы уже использовали пробный период!", show_alert=True)
    
    print(f"🎁 Создаём тестовый ключ для {callback.from_user.id}")
    sub_id = xui.add_client(callback.from_user.id, "Trial", days=2)
    print(f"Результат создания ключа: {sub_id}")
    
    if sub_id:
        await db.add_device(callback.from_user.id, "Trial", sub_id, 2)
        await db.set_trial_used(callback.from_user.id)
        link = os.getenv("VLESS_TEMPLATE").format(sub_id=sub_id)
        await callback.message.answer(f"🎁 <b>Пробный период на 2 дня!</b>\n\n🔗 Ваша подписка:\n<code>{link}</code>\n\n📅 Действует 2 дня")
        await callback.message.answer("Главное меню:", reply_markup=main_menu_kb(callback.from_user.id))
    else:
        await callback.answer("❌ Ошибка связи с сервером. Попробуйте позже или обратитесь к администратору.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    devices = await db.get_user_devices(callback.from_user.id)
    if not devices:
        txt = "<b>👤 Профиль</b>\n\nУ вас пока нет активных подписок.\nКупите подписку или возьмите пробный период!"
        await callback.message.edit_text(txt, reply_markup=main_menu_kb(callback.from_user.id))
        return
    
    txt = f"<b>👤 Профиль</b>\n\n📱 Ваши устройства ({len(devices)}/{MAX_DEVICES}):\n\n"
    for i, d in enumerate(devices, 1):
        link = os.getenv("VLESS_TEMPLATE").format(sub_id=d['uuid'])
        txt += f"{i}. <b>{d['device_name']}</b>\n"
        txt += f"   🔗 <code>{link}</code>\n"
        txt += f"   📅 Осталось: {d['days_left']} дн.\n\n"
    
    await callback.message.edit_text(txt, reply_markup=main_menu_kb(callback.from_user.id))

@dp.callback_query(F.data == "help")
async def help_info(callback: types.CallbackQuery):
    txt = "<b>⚙️ Инструкции по подключению:</b>\n\n"
    txt += "<b>📱 Android:</b>\n1. Скачайте приложение v2rayNG из Google Play\n2. Скопируйте ссылку из профиля\n3. Добавьте как 'Subscription' в приложении\n\n"
    txt += "<b>📱 iOS:</b>\n1. Скачайте приложение Streisand из App Store\n2. Скопируйте ссылку из профиля\n3. Добавьте новую подписку\n\n"
    txt += "<b>💻 Windows/Mac:</b>\n1. Скачайте v2rayN или Nekoray\n2. Импортируйте конфигурацию из буфера обмена\n\n"
    txt += "<b>🔗 Ваша ссылка для подключения:</b>\nФормат: VLESS + Reality"
    
    await callback.message.edit_text(txt, reply_markup=main_menu_kb(callback.from_user.id))

@dp.callback_query(F.data == "support")
async def support(callback: types.CallbackQuery):
    txt = "<b>🆘 Поддержка</b>\n\nПо всем вопросам обращайтесь к администратору:\n@kent_proxy_support"
    await callback.message.edit_text(txt, reply_markup=main_menu_kb(callback.from_user.id))

@dp.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Доступ запрещен", show_alert=True)
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    builder.row(types.InlineKeyboardButton(text="📝 Список пользователей", callback_data="admin_users"))
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    
    await callback.message.edit_text("<b>👑 Админ-панель</b>", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Доступ запрещен", show_alert=True)
    
    total_users = await db.get_total_users()
    total_devices = await db.get_total_devices()
    active_trials = await db.get_active_trials()
    
    txt = f"<b>📊 Статистика</b>\n\n"
    txt += f"👥 Всего пользователей: {total_users}\n"
    txt += f"📱 Всего устройств: {total_devices}\n"
    txt += f"🎁 Активных триалов: {active_trials}"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Доступ запрещен", show_alert=True)
    
    users = await db.get_all_users_with_devices()
    if not users:
        txt = "Нет пользователей"
    else:
        txt = "<b>📝 Список пользователей:</b>\n\n"
        for user in users[:20]:  # Показываем первых 20
            txt += f"👤 ID: {user['user_id']}\n"
            txt += f"📱 Устройств: {user['devices_count']}\n"
            txt += "—————————\n"
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel"))
    
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

# --- ЗАПУСК ---

async def main():
    await db.init_db()
    print("🚀 Бот KENTVPN запущен!")
    print(f"📊 Admin IDs: {ADMIN_IDS}")
    print(f"🔗 Панель: {os.getenv('PANEL_URL')}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())