import requests
import os
import uuid
import json
from dotenv import load_dotenv

load_dotenv()

class XUI:
    def __init__(self):
        # Убедись, что в .env HOST без лишних пробелов и слешей в конце
        self.host = os.getenv("XUI_HOST").strip().rstrip('/')
        self.username = os.getenv("XUI_USER")
        self.password = os.getenv("XUI_PASS")
        self.session = requests.Session()
        
        print(f"[XUI DEBUG] Инициализация: Host={self.host}, User={self.username}")

    def login(self):
        try:
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            print(f"[XUI DEBUG] Попытка логина: {url}")
            
            response = self.session.post(url, data=data, timeout=15)
            
            # Проверяем, что ответил сервер
            if response.status_code != 200:
                print(f"[XUI DEBUG] Сервер ответил кодом: {response.status_code}")
                return False
                
            res_json = response.json()
            print(f"[XUI DEBUG] Ответ логина: {res_json}")
            return res_json.get("success", False)
            
        except Exception as e:
            print(f"[XUI DEBUG] КРИТИЧЕСКАЯ ОШИБКА ЛОГИНА: {e}")
            return False

    def add_client(self, user_id, device_name):
        print(f"[XUI DEBUG] Начало процесса add_client для {user_id}")
        
        if not self.login():
            print("[XUI DEBUG] Остановка: логин не удался.")
            return None
            
        new_uuid = str(uuid.uuid4())
        # Проверь ID инбаунда в панели! Обычно это 1.
        inbound_id = 1 
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Структура JSON для 3X-UI (MHSanaei)
        client_data = {
            "id": new_uuid,
            "alterId": 0,
            "email": f"{user_id}_{device_name}",
            "limitIp": 0,
            "totalGB": 0,
            "expiryTime": 0,
            "enable": True,
            "tgId": str(user_id),
            "subId": ""
        }
        
        payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [client_data]})
        }
        
        print(f"[XUI DEBUG] Отправка запроса на добавление: {url}")
        
        try:
            response = self.session.post(url, json=payload, timeout=15)
            print(f"[XUI DEBUG] Статус ответа API: {response.status_code}")
            
            res_data = response.json()
            print(f"[XUI DEBUG] Данные ответа API: {res_data}")
            
            if res_data.get("success"):
                print(f"[XUI DEBUG] КЛИЕНТ УСПЕШНО СОЗДАН: {new_uuid}")
                return new_uuid
            else:
                print(f"[XUI DEBUG] ОШИБКА ПАНЕЛИ: {res_data.get('msg')}")
                return None
                
        except Exception as e:
            print(f"[XUI DEBUG] ОШИБКА ЗАПРОСА API: {e}")
            return None
