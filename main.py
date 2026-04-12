import requests
import os
import uuid
import json
import time
import urllib3
import sys
from dotenv import load_dotenv

# Отключаем предупреждения о небезопасном SSL (так как используем IP вместо домена)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        # Очищаем URL от лишних пробелов и слешей в конце
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        
        # Заголовки, чтобы панель принимала запросы как от браузера
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json"
        })
        
        print(f"!!! [SYSTEM] КЛАСС XUI ЗАГРУЖЕН | РАБОТАЕМ С ID: {self.inbound_id} !!!")
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
            print(f"[DEBUG] Ошибка авторизации: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        print(f"!!! [DEBUG] ВЫЗВАН МЕТОД add_client ДЛЯ {user_id} !!!")
        sys.stdout.flush()
        
        if not self.login():
            print("[DEBUG] Не удалось войти в панель")
            return None
            
        new_uuid = str(uuid.uuid4())
        # Создаем subId — он нужен для формирования "зеленой" ссылки-подписки
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        client_email = f"KENT_{user_id}_{int(time.time())%1000}"
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Настройки клиента. ВАЖНО: flow установлен в xtls-rprx-vision
        client_dict = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision",
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
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_data = response.json()
            
            print(f"[DEBUG] ОТВЕТ ПАНЕЛИ: {res_data}")
            sys.stdout.flush()
            
            if res_data.get("success"):
                # Возвращаем именно subscription_id для использования в ссылке
                return subscription_id
            return None
        except Exception as e:
            print(f"[DEBUG] Ошибка запроса к API: {e}")
            sys.stdout.flush()
            return None
