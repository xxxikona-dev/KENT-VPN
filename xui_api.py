import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем надоедливые предупреждения об отсутствии SSL-сертификата в консоли
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

class XUI:
    def __init__(self):
        # Очищаем URL от лишних пробелов и слешей
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        
        # Печатаем конфиг для проверки в терминале при запуске
        print(f"[XUI] Загружен: {self.host} | Inbound ID: {self.inbound_id}")

    def login(self):
        """Авторизация в панели 3X-UI"""
        try:
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            
            # verify=False игнорирует отсутствие SSL на IP-адресе
            response = self.session.post(url, data=data, timeout=10, verify=False)
            
            if response.status_code == 200:
                res_json = response.json()
                return res_json.get("success", False)
            return False
        except Exception as e:
            print(f"[XUI Error] Ошибка логина: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        """Создает нового клиента в панели и возвращает его UUID"""
        if not self.login():
            print("[XUI Error] Не удалось войти в панель")
            return None
            
        new_uuid = str(uuid.uuid4())
        # Время истечения: текущее время + дни в миллисекундах
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        # Генерируем уникальный email, чтобы не было конфликтов
        # Например: user_5153650495_a1b2
        short_id = str(uuid.uuid4())[:4]
        client_email = f"user_{user_id}_{short_id}"
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Настройки клиента для 3X-UI (VLESS Reality)
        client_dict = {
            "id": new_uuid,
            "flow": "",
            "email": client_email,
            "limitIp": 2, # Лимит: 2 одновременных подключения
            "totalGB": 0, # 0 = безлимит по трафику
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": ""
        }
        
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_dict]})
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_data = response.json()
            
            if res_data.get("success"):
                print(f"[XUI Success] Клиент создан: {client_email}")
                return new_uuid
            else:
                # Если здесь ошибка "Inbound not found", проверь INBOUND_ID в .env
                print(f"[XUI Error] Панель отклонила: {res_data.get('msg')}")
                return None
        except Exception as e:
            print(f"[XUI Error] Ошибка запроса: {e}")
            return None
