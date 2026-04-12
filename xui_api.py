import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Полностью отключаем логи об SSL, чтобы видеть только важные данные
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

class XUI:
    def __init__(self):
        # Очистка URL: убираем лишние пробелы и финальные слеши
        raw_url = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.host = raw_url
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        
        print(f"[DEBUG] XUI Инициализирован. URL: {self.host}")

    def login(self):
        """Метод авторизации с выводом ответа сервера в консоль"""
        try:
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            
            response = self.session.post(url, data=data, timeout=10, verify=False)
            
            # Если сервер ответил не 200, значит путь PANEL_URL указан неверно
            if response.status_code != 200:
                print(f"[DEBUG] Ошибка логина! Статус: {response.status_code}. Проверь PANEL_URL.")
                return False
                
            res_json = response.json()
            if not res_json.get("success"):
                print(f"[DEBUG] Панель отклонила логин/пароль: {res_json}")
                return False
                
            return True
        except Exception as e:
            print(f"[DEBUG] Ошибка подключения к серверу: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        """Метод добавления клиента"""
        if not self.login():
            return None
            
        new_uuid = str(uuid.uuid4())
        # Время в мс для 3X-UI
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        # Email должен быть уникальным, иначе панель выдаст ошибку
        client_email = f"ID{user_id}_{int(time.time()) % 10000}"
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        client_dict = {
            "id": new_uuid,
            "flow": "",
            "email": client_email,
            "limitIp": 2,
            "totalGB": 0,
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
            
            # Печатаем ответ в терминал, чтобы видеть причину, если в панели 'пусто'
            print(f"[DEBUG] Ответ на addClient: {res_data}")
            
            if res_data.get("success"):
                print(f"✅ Успех! Ключ создан для {user_id}")
                return new_uuid
            else:
                print(f"❌ Панель отказала: {res_data.get('msg')}")
                return None
        except Exception as e:
            print(f"[DEBUG] Ошибка запроса API: {e}")
            return None
