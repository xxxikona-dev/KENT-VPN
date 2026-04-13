import asyncio
import os
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Подключаем твои модули
import database as db
from xui_api import XUI

# Настройка логирования в консоль
logging.basicConfig(level=logging.INFO)

# Грузим конфиг из .env
load_dotenv()

# --- КОНФИГУРАЦИЯ БОТА ---
ADMIN_IDS = [5153650495]
CHANNEL_ID = "@kent_proxy"
CHANNEL_URL = "https://t.me/kent_proxy"
# Твой базовый домен или IP для ссылок (из настроек панели)
BASE_SUB_URL = "https://91.199.32.144:2096/sub"

# Инициализация бота и диспетчера
bot = Bot(
    token=os.getenv("BOT_TOKEN"), 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
xui = XUI()

# --- ФУНКЦИИ И КЛАВИАТУРЫ ---

async def check_subscription(user_id: int):
    """Проверяет, подписан ли пользователь на обязательный канал"""
    if user_id in ADMIN_IDS:
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return False

def main_menu_kb(user_id: int):
    """Создает главную клавиатуру бота"""
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💎 Купить подписку", callback_data="buy_menu"))
    builder.row(types.InlineKeyboardButton(text="🎁 Тест на 2 дня", callback_data="take_trial"))
    builder.row(types.InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
                types.InlineKeyboardButton(text="⚙️ Инструкции", callback_data="help"))
    
    # Кнопка админки только для своих
    if user_id in ADMIN_IDS:
        builder.row(types.InlineKeyboardButton(text="👑 Админка", callback_data="admin_panel"))
    
    return builder.as_markup()

# --- ОБРАБОТЧИКИ (ХЕНДЛЕРЫ) ---

@dp.message(Command("start"))
@dp.callback_query(F.data == "start_over")
async def cmd_start(event: types.Message | types.CallbackQuery):
    """Запуск бота или возврат в главное меню"""
    user_id = event.from_user.id
    
    # Проверка подписки на канал
    if not await check_subscription(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Подписаться на канал", url=CHANNEL_URL))
        builder.row(types.InlineKeyboardButton(text="✅ Я подписался", callback_data="start_over"))
        
        txt = "<b>🚫 Доступ ограничен!</b>\n\nПодпишись на наш канал, чтобы пользоваться ботом и получать обновления."
        
        if isinstance(event, types.Message):
            return await event.answer(txt, reply_markup=builder.as_markup())
        return await event.message.edit_text(txt, reply_markup=builder.as_markup())

    # Главное приветствие БЕЗ названия KENT-VPN
    txt = "<b>🚀 Готов к безопасному серфингу!</b>\n\nВыбирай нужный раздел в меню ниже:"
    kb = main_menu_kb(user_id)
    
    if isinstance(event, types.Message):
        await event.answer(txt, reply_markup=kb)
    else:
        # Пытаемся отредактировать старое сообщение, если не получается — шлем новое
        try:
            await event.message.edit_text(txt, reply_markup=kb)
        except:
            await event.message.answer(txt, reply_markup=kb)

@dp.callback_query(F.data == "take_trial")
async def process_trial(callback: types.CallbackQuery):
    """Выдача бесплатного теста на 48 часов"""
    user_id = callback.from_user.id
    
    # Проверка в локальной БД бота
    if await db.check_trial(user_id):
        return await callback.answer("❌ Вы уже использовали тестовый период!", show_alert=True)
    
    # Обращение к панели (задаем ровно 2 дня)
    sub_id = xui.add_client(user_id, days=2)
    
    if sub_id:
        # Фиксируем выдачу в базе
        await db.add_device(user_id, "Тестовый доступ", sub_id, 2)
        await db.set_trial_used(user_id)
        
        link = f"{BASE_SUB_URL}/{sub_id}"
        
        await callback.message.answer(
            f"🎁 <b>Тестовый период (2 дня) активирован!</b>\n\n"
            f"Твоя ссылка для подключения:\n"
            f"<code>{link}</code>\n\n"
            f"Просто скопируй её и вставь в Streisand.",
            reply_markup=main_menu_kb(user_id)
        )
    else:
        await callback.answer("⚠️ Ошибка сервера. Попробуй позже.", show_alert=True)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    """Раздел личного кабинета пользователя"""
    devices = await db.get_user_devices(callback.from_user.id)
    
    txt = "<b>👤 Ваш профиль</b>\n\n"
    if not devices:
        txt += "У вас пока нет активных подписок."
    else:
        txt += "Ваши активные ссылки:\n\n"
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
        "1. Установи <b>Streisand</b> (iOS) или <b>v2rayNG</b> (Android).\n"
        "2. Скопируй ссылку из профиля или теста.\n"
        "3. В приложении нажми '+' и выбери импорт.\n"
        "4. Обнови список и нажми кнопку подключения."
    )
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="⬅️ Назад", callback_data="start_over"))
    await callback.message.edit_text(txt, reply_markup=builder.as_markup())

# --- ЗАПУСК ПРОГРАММЫ ---

async def main():
    # Создаем таблицы в БД, если их нет
    await db.init_db()
    logging.info("--- Бот успешно запущен и готов к работе! ---")
    
    # Начинаем опрос серверов Telegram
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен пользователем")
