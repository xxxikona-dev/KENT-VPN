import requests
import os
import uuid
import json
from dotenv import load_dotenv

load_dotenv()

class XUI:
    def __init__(self):
        # Берем URL из .env (https://91.199.32.144:2053/0gAQwcQicov4jpRgFJ/)
        base_url = os.getenv("PANEL_URL").strip().rstrip('/')
        self.host = base_url
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 1))
        self.session = requests.Session()
        
        print(f"[XUI] Инициализация. URL: {self.host}, ID: {self.inbound_id}")

    def login(self):
        try:
            # Склеиваем секретный путь с эндпоинтом логина
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            
            response = self.session.post(url, data=data, timeout=10, verify=False) # verify=False т.к. IP обычно без норм SSL
            
            # Для отладки
            if response.status_code != 200:
                print(f"[XUI] Ошибка логина! Статус: {response.status_code}")
                return False
                
            res_json = response.json()
            return res_json.get("success", False)
        except Exception as e:
            print(f"[XUI] Критическая ошибка при коннекте: {e}")
            return False

    def add_client(self, user_id, device_name):
        if not self.login():
            print("[XUI] Не удалось авторизоваться в панели.")
            return None
            
        new_uuid = str(uuid.uuid4())
        # Эндпоинт добавления тоже должен идти после секретного пути
        url = f"{self.host}/panel/api/inbounds/addClient"
        
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
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_data]})
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_data = response.json()
            
            if res_data.get("success"):
                print(f"[XUI] Клиент создан успешно: {new_uuid}")
                return new_uuid
            else:
                print(f"[XUI] Панель отклонила запрос: {res_data}")
                return None
        except Exception as e:
            print(f"[XUI] Ошибка запроса addClient: {e}")
            return None
