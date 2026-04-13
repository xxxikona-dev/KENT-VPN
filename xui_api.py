import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем ворнинги SSL, так как работаем с IP сервера напрямую
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        """Вход в панель 3X-UI"""
        try:
            url = f"{self.host}/login"
            response = self.session.post(
                url, 
                data={"username": self.username, "password": self.password}, 
                timeout=10, 
                verify=False
            )
            return response.json().get("success", False)
        except Exception as e:
            print(f"❌ Ошибка входа в панель: {e}")
            return False

    def add_client(self, user_id, days=30):
        """
        Добавление клиента в панель.
        days=2 (для теста) или days=30 (для покупки).
        """
        if not self.login():
            return None
        
        # Генерация уникальных данных для протокола VLESS
        new_uuid = str(uuid.uuid4())
        # sub_id для формирования красивой ссылки
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        
        # Название, которое отобразится в Streisand/v2rayNG
        display_name = f"🇬🇧[UK] Великобритания | {user_id}"
        
        # РАСЧЕТ СРОКА ДЕЙСТВИЯ (в миллисекундах для 3X-UI)
        # Текущее время + секунды в днях, умножаем на 1000
        expiry_time = int((time.time() + (int(days) * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Основной объект настроек клиента
        client_dict = {
            "id": new_uuid,
            "email": display_name,
            "limitIp": 2,
            "totalGB": 0,
            "expiryTime": expiry_time, # Срок действия подставляется из переданных дней
            "enable": True,
            "tgId": str(user_id),
            "subId": subscription_id
        }
        
        # Упаковка для API (поле Flow НЕ ПЕРЕДАЕМ, оно должно быть пустым)
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_dict]})
        }
        
        try:
            response = self.session.post(
                url, 
                json=payload, 
                timeout=10, 
                verify=False
            )
            res_json = response.json()
            
            # Лог для тебя в консоли
            print(f"--- Создание клиента ---")
            print(f"Дней: {days} | ID: {user_id} | Результат: {res_json.get('success')}")
            
            if res_json.get("success"):
                return subscription_id
            else:
                print(f"❌ Ошибка панели: {res_json.get('msg')}")
                return None
                
        except Exception as e:
            print(f"❌ Критическая ошибка при добавлении: {e}")
            return None
