import aiosqlite
import time

DB_PATH = "vpn_bot.db"

async def init_db():
    """Инициализация базы данных и создание таблиц"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                trial_used INTEGER DEFAULT 0,
                registration_date INTEGER
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                device_name TEXT,
                uuid TEXT,
                expiry_date INTEGER,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        await db.commit()

async def add_user_if_not_exists(user_id):
    """Регистрирует пользователя, если его нет в базе"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, registration_date) VALUES (?, ?)",
            (user_id, int(time.time()))
        )
        await db.commit()

async def check_trial(user_id):
    """Проверяет, использовал ли пользователь пробный период"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT trial_used FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] == 1 if row else False

async def set_trial_used(user_id):
    """Отмечает использование триала"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, trial_used, registration_date) VALUES (?, 1, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET trial_used = 1",
            (user_id, int(time.time()))
        )
        await db.commit()

async def add_device(user_id, device_name, u_uuid, expiry_days):
    """Добавляет устройство с расчетом даты истечения"""
    expiry_date = int(time.time()) + (expiry_days * 86400)
    async with aiosqlite.connect(DB_PATH) as db:
        await add_user_if_not_exists(user_id)
        await db.execute(
            "INSERT INTO devices (user_id, device_name, uuid, expiry_date) VALUES (?, ?, ?, ?)",
            (user_id, device_name, u_uuid, expiry_date)
        )
        await db.commit()

async def get_user_devices(user_id):
    """Получает список устройств в виде словарей"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM devices WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
