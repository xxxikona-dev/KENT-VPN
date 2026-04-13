import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Игнорируем ошибки сертификатов, так как работаем с IP напрямую
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        # URL панели из .env (например, http://91.199.32.144:2096)
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        # Твой Inbound KENT-VPN имеет ID 3
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        """Вход в панель для получения сессии"""
        try:
            url = f"{self.host}/login"
            response = self.session.post(
                url, 
                data={"username": self.username, "password": self.password}, 
                timeout=10, 
                verify=False
            )
            return response.json().get("success", False)
        except Exception as e:
            print(f"Ошибка авторизации: {e}")
            return False

    def add_client(self, user_id):
        """Имитация нажатия кнопки 'Добавить клиента' как на твоем скрине"""
        if not self.login():
            return None
        
        # Генерируем стандартные поля, которые требует форма на скрине
        client_uuid = str(uuid.uuid4()) # Поле ID
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16] # Поле Subscription
        # Поле Email (делаем уникальным, чтобы панель не ругалась)
        email = f"u{subscription_id[:7]}" 
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Формируем объект клиента точно по структуре 3X-UI
        client_data = {
            "id": client_uuid,
            "flow": "xtls-rprx-vision", # Стандарт для твоего Reality
            "email": email,
            "limitIp": 2,
            "totalGB": 0,
            "expiryTime": 0, # Без лимита по времени (или настрой по желанию)
            "enable": True,
            "tgId": str(user_id),
            "subId": subscription_id
        }
        
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_data]})
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            result = response.json()
            
            if result.get("success"):
                print(f"✅ Клиент {email} успешно добавлен в Inbound {self.inbound_id}")
                return subscription_id
            else:
                print(f"❌ Панель отклонила запрос: {result.get('msg')}")
                return None
        except Exception as e:
            print(f"❌ Ошибка при отправке запроса: {e}")
            return None
