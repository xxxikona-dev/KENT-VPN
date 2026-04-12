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
        print("!!! [SYSTEM] КЛАСС XUI ЗАГРУЖЕН !!!")
        sys.stdout.flush()

    def login(self):
        print(f"[DEBUG] Пытаюсь зайти: {self.host}/login")
        sys.stdout.flush()
        try:
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            response = self.session.post(url, data=data, timeout=10, verify=False)
            
            print(f"[DEBUG] Статус логина: {response.status_code}")
            sys.stdout.flush()
            
            if response.status_code == 200:
                res = response.json()
                print(f"[DEBUG] JSON логина: {res}")
                sys.stdout.flush()
                return res.get("success", False)
            return False
        except Exception as e:
            print(f"[DEBUG] Ошибка коннекта: {e}")
            sys.stdout.flush()
            return False

    def add_client(self, user_id, device_name, days=30):
        print(f"!!! [DEBUG] ВЫЗВАН METOД add_client ДЛЯ {user_id} !!!")
        sys.stdout.flush()
        
        if not self.login():
            print("[DEBUG] Логин не прошел, выходим")
            sys.stdout.flush()
            return None
            
        new_uuid = str(uuid.uuid4())
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        client_email = f"KENT_{user_id}_{int(time.time())%1000}"
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({
                "clients": [{
                    "id": new_uuid,
                    "flow": "",
                    "email": client_email,
                    "limitIp": 2,
                    "totalGB": 0,
                    "expiryTime": expiry_time,
                    "enable": True,
                    "tgId": str(user_id),
                    "subId": ""
                }]
            })
        }
        
        try:
            print(f"[DEBUG] Отправка запроса в инбаунд {self.inbound_id}...")
            sys.stdout.flush()
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_data = response.json()
            print(f"[DEBUG] ОТВЕТ ПАНЕЛИ: {res_data}")
            sys.stdout.flush()
            
            if res_data.get("success"):
                return new_uuid
            return None
        except Exception as e:
            print(f"[DEBUG] Ошибка API: {e}")
            sys.stdout.flush()
            return None
