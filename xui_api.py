import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем предупреждения об отсутствии SSL, так как панель на HTTP
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        # Базовый URL панели (из переменной окружения)
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        # ID входящего подключения (из скринов это ID 3)
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json"
        })

    def login(self):
        """Авторизация в панели 3X-UI"""
        try:
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            response = self.session.post(url, data=data, timeout=10, verify=False)
            return response.json().get("success", False)
        except Exception as e:
            print(f"Ошибка логина: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        """
        Создает нового клиента в Inbound.
        Возвращает subId (идентификатор подписки), если успешно.
        """
        if not self.login():
            return None

        # Генерируем уникальные данные для клиента
        new_uuid = str(uuid.uuid4())
        # subId — это то, что идет в ссылку подписки
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        # Время истечения в миллисекундах
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        # Красивое имя клиента для отображения в списке панели
        client_email = f"KENT_{device_name}_{user_id}"

        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Формируем структуру клиента согласно API 3X-UI
        client_dict = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision", # Для Reality + Vision
            "email": client_email,
            "limitIp": 2,               # Ограничение на 2 устройства
            "totalGB": 0,               # 0 = безлимит
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": subscription_id
        }

        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_dict]})
        }

        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            result = response.json()
            if result.get("success"):
                return subscription_id
            else:
                print(f"Ошибка API: {result.get('msg')}")
                return None
        except Exception as e:
            print(f"Ошибка при добавлении клиента: {e}")
            return None

    def get_client_stats(self, email):
        """(Опционально) Получение трафика клиента по email"""
        if not self.login():
            return None
        url = f"{self.host}/panel/api/inbounds/getClientTraffics/{email}"
        try:
            response = self.session.get(url, timeout=10, verify=False)
            return response.json().get("obj")
        except:
            return None
