import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Игнорируем предупреждения об отсутствии SSL (для работы по прямому IP)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        # Ставим заголовки, чтобы панель принимала нас за браузер
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        """Вход в панель и сохранение Cookies в сессии"""
        try:
            url = f"{self.host}/login"
            response = self.session.post(
                url, 
                data={"username": self.username, "password": self.password}, 
                timeout=10, 
                verify=False
            )
            res_json = response.json()
            return res_json.get("success", False)
        except Exception as e:
            print(f"❌ Критическая ошибка логина: {e}")
            return False

    def add_client(self, user_id, device_name="Device", days=30):
        """
        Добавляет клиента в панель.
        Flow оставляем пустым, чтобы работало автоматически.
        Email используем как название локации.
        """
        if not self.login():
            return None
        
        # Генерируем уникальные идентификаторы
        new_uuid = str(uuid.uuid4())
        # sub_id - это то, что будет в конце ссылки /sub/xxxx
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        
        # Название подписки. Используем ID пользователя для уникальности в базе,
        # но в самом приложении будет видно "Великобритания".
        display_name = f"[UK] Великобритания | {user_id}"
        
        # Рассчитываем дату окончания
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Формируем настройки клиента БЕЗ ПОЛЯ FLOW
        client_dict = {
            "id": new_uuid,
            "email": display_name,
            "limitIp": 2,
            "totalGB": 0,
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": subscription_id
        }
        
        # Данные для отправки в панель
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
            
            # Отладочный вывод в консоль
            print(f"--- Результат для пользователя {user_id} ---")
            print(json.dumps(res_json, indent=2, ensure_ascii=False))
            
            if res_json.get("success"):
                return subscription_id
            else:
                return None
                
        except Exception as e:
            print(f"❌ Ошибка при отправке запроса addClient: {e}")
            return None
