import requests
import os
import uuid
import json
import time
import urllib3
import random
import string
from dotenv import load_dotenv

# Отключаем предупреждения SSL, так как работаем с панелью напрямую по IP
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Загружаем переменные окружения из .env
load_dotenv()

class XUI:
    def __init__(self):
        """Инициализация параметров подключения к панели 3X-UI"""
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        # Заголовки для имитации запроса из браузера
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def login(self):
        """Авторизация в панели и получение Cookies"""
        try:
            url = f"{self.host}/login"
            data = {
                "username": self.username,
                "password": self.password
            }
            response = self.session.post(url, data=data, timeout=10, verify=False)
            result = response.json()
            if result.get("success"):
                logging.info("Успешная авторизация в панели 3X-UI")
                return True
            else:
                logging.error(f"Ошибка авторизации: {result.get('msg')}")
                return False
        except Exception as e:
            logging.error(f"Критическая ошибка подключения к панели: {e}")
            return False

    def add_client(self, user_id, days=30):
        """
        Добавление нового клиента VLESS.
        user_id: ID пользователя в Telegram
        days: количество дней (2 для теста, 30 для покупки)
        """
        if not self.login():
            return None
        
        # Генерируем уникальный UUID для протокола
        new_uuid = str(uuid.uuid4())
        
        # Генерируем случайный ID подписки (для ссылки /sub/xxxx)
        subscription_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        
        # --- ЛОГИКА МАСКИРОВКИ ---
        # Используем 50 неразрывных пробелов, чтобы в Streisand текст ушел за экран.
        # В начале будет стоять только Remark из настроек Inbound в самой панели.
        invisible_padding = " " * 50 
        short_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=4))
        display_email = f"{invisible_padding}id{short_id}" 

        # Рассчитываем время истечения в миллисекундах (текущее время + секунды в днях * 1000)
        expiry_time = int((time.time() + (int(days) * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Конфигурация нового клиента
        client_dict = {
            "id": new_uuid,
            "email": display_email,
            "limitIp": 2,      # Ограничение на 2 одновременных IP
            "totalGB": 0,      # 0 означает безлимитный трафик
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": subscription_id
        }
        
        # Оборачиваем настройки в JSON (поле flow НЕ передаем, чтобы работало везде)
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_dict]})
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_json = response.json()
            
            # Логируем ответ для отладки
            print(f"--- Результат добавления клиента (User: {user_id}, Days: {days}) ---")
            print(json.dumps(res_json, indent=2, ensure_ascii=False))
            
            if res_json.get("success"):
                return subscription_id
            else:
                return None
        except Exception as e:
            print(f"Ошибка при вызове addClient: {e}")
            return None

import logging
logging.basicConfig(level=logging.INFO)
