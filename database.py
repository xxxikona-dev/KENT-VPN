import aiosqlite
import time

DB_PATH = "vpn_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Таблица устройств
        await db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                device_name TEXT,
                uuid TEXT,
                expiry_date INTEGER
            )
        """)
        # Таблица пользователей для триалов и админки
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                is_trial_used INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def add_device(user_id, device_name, uuid, expiry_days=30):
    expiry_date = int(time.time() + expiry_days * 86400)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO devices (user_id, device_name, uuid, expiry_date) VALUES (?, ?, ?, ?)",
            (user_id, device_name, uuid, expiry_date)
        )
        await db.commit()

async def get_user_devices(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM devices WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchall()

async def check_trial(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_trial_used FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return False
            return bool(row[0])

async def set_trial_used(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET is_trial_used = 1 WHERE user_id = ?", (user_id,))
        await db.commit()
