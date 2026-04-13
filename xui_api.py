import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем предупреждения SSL для работы по IP
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        # URL твоей панели из .env (например, https://91.199.32.144:2096)
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        # ID твоего Inbound (у тебя это 3)
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        """Авторизация в панели для получения сессии"""
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

    def add_client(self, user_id, device_name="Device", days=30):
        """
        Добавление клиента с чистым названием [UK] Великобритания.
        Flow оставляем пустым, как мы выяснили — так работает.
        """
        if not self.login():
            return None
        
        # Генерируем UUID и ID подписки
        new_uuid = str(uuid.uuid4())
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        
        # --- НАСТРОЙКА ИМЕНИ ---
        # Чтобы не было цифр в приложении, мы используем спецсимвол или 
        # скрываем ID пользователя в Email, чтобы панель разрешила создание.
        # В большинстве приложений будет отображаться только часть до спецсимвола.
        client_email = f"[UK] Великобритания | {user_id}"
        
        # Рассчитываем время жизни (30 дней по умолчанию)
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Формируем данные клиента
        client_dict = {
            "id": new_uuid,
            "email": client_email, # Это станет названием прокси в Streisand
            "limitIp": 2,          # Лимит на 2 устройства
            "totalGB": 0,          # Безлимит трафика
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": subscription_id
        }
        
        # Отправляем JSON в панель
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_dict]})
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            res_json = response.json()
            
            # Логируем результат в консоль
            print(f"--- Создание клиента для TG:{user_id} ---")
            print(json.dumps(res_json, indent=2, ensure_ascii=False))
            
            if res_json.get("success"):
                return subscription_id
            else:
                # Если такой Email уже есть, добавим немного рандома (защита от ошибок)
                client_dict["email"] = f"[UK] Великобритания ({str(uuid.uuid4())[:4]})"
                payload["settings"] = json.dumps({"clients": [client_dict]})
                retry_response = self.session.post(url, json=payload, timeout=10, verify=False)
                if retry_response.json().get("success"):
                    return subscription_id
                return None
                
        except Exception as e:
            print(f"❌ Ошибка запроса addClient: {e}")
            return None
