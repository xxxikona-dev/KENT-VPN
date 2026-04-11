import aiosqlite
import time

async def init_db():
    async with aiosqlite.connect("vpn_bot.db") as db:
        # Таблица подписок (основная)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                device_name TEXT,
                uuid TEXT,
                expiry_date INTEGER,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.commit()

async def get_user_devices(user_id):
    async with aiosqlite.connect("vpn_bot.db") as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM devices WHERE user_id = ? AND is_active = 1", (user_id,)) as cursor:
            return await cursor.fetchall()

async def add_device(user_id, device_name, uuid, days=30):
    expiry = int(time.time() + days * 86400)
    async with aiosqlite.connect("vpn_bot.db") as db:
        await db.execute(
            "INSERT INTO devices (user_id, device_name, uuid, expiry_date) VALUES (?, ?, ?, ?)",
            (user_id, device_name, uuid, expiry)
        )
        await db.commit()
