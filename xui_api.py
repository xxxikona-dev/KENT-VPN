import requests
import os
import uuid
import json
import time
import urllib3
import sys
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        
        # Эмуляция браузера для корректной работы API
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
            "Accept": "application/json"
        })
        
        print(f"!!! [SYSTEM] XUI ЗАГРУЖЕН | ID: {self.inbound_id} !!!")
        sys.stdout.flush()

    def login(self):
        try:
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            response = self.session.post(url, data=data, timeout=10, verify=False)
            
            if response.status_code == 200:
                res = response.json()
                return res.get("success", False)
            return False
        except Exception as e:
            print(f"[DEBUG] Ошибка логина: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        print(f"!!! [DEBUG] СОЗДАНИЕ КЛИЕНТА ДЛЯ {user_id} !!!")
        sys.stdout.flush()
        
        if not self.login():
            return None
            
        new_uuid = str(uuid.uuid4())
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        client_email = f"KENT_{user_id}_{int(time.time())%1000}"
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Настройки Vision Reality TCP
        client_dict = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision",
            "email": client_email,
            "limitIp": 2,
            "totalGB": 0,
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": str(uuid.uuid4()).replace('-', '')[:16] # Генерация ID подписки
        }
        
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_dict]})
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_data = response.json()
            
            if res_data.get("success"):
                print(f"[DEBUG] УСПЕХ: Клиент создан")
                sys.stdout.flush()
                return new_uuid
            return None
        except Exception as e:
            print(f"[DEBUG] Ошибка запроса: {e}")
            sys.stdout.flush()
            return None
