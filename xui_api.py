import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем предупреждения о небезопасном соединении (актуально для IP без SSL)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        # Отрезаем лишние слэши в конце URL, если они есть
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        """Авторизация в панели"""
        try:
            url = f"{self.host}/login"
            response = self.session.post(
                url, 
                data={"username": self.username, "password": self.password}, 
                timeout=10, 
                verify=False
            )
            res_json = response.json()
            if not res_json.get("success"):
                print(f"❌ Ошибка входа в панель: {res_json.get('msg')}")
            return res_json.get("success", False)
        except Exception as e:
            print(f"❌ Ошибка подключения при логине: {e}")
            return False

    def add_client(self, user_id, device_name="Device", days=30):
        """Добавление клиента точно так же, как через кнопку в браузере"""
        if not self.login():
            return None
        
        # Генерируем данные клиента, как это делает интерфейс панели
        new_uuid = str(uuid.uuid4())
        # sub_id — это то, что идет в конце ссылки /sub/XXXXXXXXXXXXXXXX
        sub_id = str(uuid.uuid4()).replace('-', '')[:16]
        # Делаем почту клиента уникальной, добавляя часть UUID
        client_email = f"KENT_{user_id}_{str(uuid.uuid4())[:4]}"
        # Рассчитываем время истечения в миллисекундах
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Полный словарь настроек клиента (идентично ручному вводу)
        client_dict = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision", # Обязательно для Reality
            "email": client_email,
            "limitIp": 2,
            "totalGB": 0,
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": sub_id
        }
        
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_dict]})
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_json = response.json()
            
            # Печатаем ответ панели в консоль для отладки
            print(f"--- Ответ панели (Add Client) ---")
            print(json.dumps(res_json, indent=2, ensure_ascii=False))
            
            if res_json.get("success"):
                return sub_id
            else:
                return None
        except Exception as e:
            print(f"❌ Ошибка запроса addClient: {e}")
            return None
