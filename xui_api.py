import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем предупреждения об отсутствии SSL-сертификата при обращении по IP
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        # URL твоей панели (например, https://91.199.32.144:2096)
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        # ID твоего Inbound (судя по скринам, это 3)
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        """Авторизация в панели для получения Cookies"""
        try:
            url = f"{self.host}/login"
            response = self.session.post(
                url, 
                data={
                    "username": self.username, 
                    "password": self.password
                }, 
                timeout=10, 
                verify=False
            )
            res_json = response.json()
            if res_json.get("success"):
                return True
            else:
                print(f"❌ Ошибка входа: {res_json.get('msg')}")
                return False
        except Exception as e:
            print(f"❌ Ошибка соединения с панелью при логине: {e}")
            return False

    def add_client(self, user_id, device_name="Device", days=30):
        """
        Добавление клиента. 
        Поле Flow оставлено пустым, так как твоя панель 
        подставляет параметры автоматически.
        """
        if not self.login():
            return None
        
        # Генерация уникальных данных клиента
        new_uuid = str(uuid.uuid4())
        # sub_id — уникальный хвост для ссылки подписки
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        # Email клиента (уникальное имя в списке панели)
        client_email = f"KENT_{user_id}_{str(uuid.uuid4())[:4]}"
        # Время истечения в миллисекундах
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        # Словарь клиента. Flow НЕ УКАЗЫВАЕМ, чтобы было 'Пусто'
        client_dict = {
            "id": new_uuid,
            "email": client_email,
            "limitIp": 2,
            "totalGB": 0,
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": subscription_id
        }
        
        # Упаковываем в структуру, которую ждет API панели
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
            
            # Лог в консоль для проверки
            print(f"--- Ответ панели для пользователя {user_id} ---")
            print(json.dumps(res_json, indent=2, ensure_ascii=False))
            
            if res_json.get("success"):
                # Возвращаем subId, чтобы main.py собрал ссылку
                return subscription_id
            else:
                print(f"❌ Панель вернула ошибку: {res_json.get('msg')}")
                return None
                
        except Exception as e:
            print(f"❌ Критическая ошибка при добавлении клиента: {e}")
            return None

    def get_client_usage(self, email):
        """Дополнительный метод: получение статистики (если понадобится)"""
        if not self.login():
            return None
            
        url = f"{self.host}/panel/api/inbounds/getClientTraffics/{email}"
        try:
            response = self.session.get(url, timeout=10, verify=False)
            return response.json()
        except:
            return None
