import requests
import os
import uuid
import json
import time
import urllib3
import sys
from dotenv import load_dotenv

# Отключаем ворнинги SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        
        # Заголовки имитации браузера
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        })

    def login(self):
        try:
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            response = self.session.post(url, data=data, timeout=10, verify=False)
            if response.status_code == 200:
                return response.json().get("success", False)
            return False
        except Exception as e:
            print(f"[DEBUG] Ошибка входа в панель: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        if not self.login():
            return None
            
        new_uuid = str(uuid.uuid4())
        # Генерируем subId (16 символов без дефисов)
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Формируем объект клиента для 3X-UI
        client_dict = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision",
            "email": f"KENT_{user_id}_{int(time.time())%1000}",
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
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_data = response.json()
            if res_data.get("success"):
                # Возвращаем именно subId для формирования ссылки
                return subscription_id
            return None
        except Exception as e:
            print(f"[DEBUG] Ошибка addClient: {e}")
            return None
