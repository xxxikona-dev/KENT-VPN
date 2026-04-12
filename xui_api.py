import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем проверку SSL, так как на панели может быть самоподписанный сертификат
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        # Важно для работы через HTTPS
        self.session.verify = False 
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        try:
            url = f"{self.host}/login"
            response = self.session.post(
                url, 
                data={"username": self.username, "password": self.password}, 
                timeout=10
            )
            # Проверяем статус ответа
            if response.status_code != 200:
                print(f"Ошибка логина: Статус {response.status_code}")
                return False
            return response.json().get("success", False)
        except Exception as e:
            print(f"Критическая ошибка логина: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        if not self.login():
            print("Не удалось авторизоваться в панели для добавления клиента")
            return None
        
        new_uuid = str(uuid.uuid4())
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        client_email = f"KENT_{device_name}_{user_id}"
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Полный набор настроек для Reality, чтобы ожил пинг
        client_dict = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision", # Это ключ к пингу в Reality
            "email": client_email,
            "limitIp": 2,
            "totalGB": 0,
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
            response = self.session.post(url, json=payload, timeout=10)
            res_json = response.json()
            if res_json.get("success"):
                return subscription_id
            else:
                print(f"Панель вернула ошибку: {res_json.get('msg')}")
                return None
        except Exception as e:
            print(f"Ошибка запроса addClient: {e}")
            return None
