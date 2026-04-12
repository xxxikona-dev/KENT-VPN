import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем проверку SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        try:
            # Для 3x-ui с нестандартным путём
            url = f"{self.host}/login"
            print(f"🔐 Логинимся: {url}")
            
            response = self.session.post(
                url, 
                data={"username": self.username, "password": self.password}, 
                timeout=10
            )
            
            print(f"📡 Статус: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    result = response.json()
                    if result.get("success"):
                        print("✅ Логин успешен")
                        return True
                except:
                    # Иногда 3x-ui возвращает HTML даже при успехе
                    if "dashboard" in response.text.lower():
                        print("✅ Логин успешен (по HTML)")
                        return True
            
            print(f"❌ Ошибка логина: {response.text[:100]}")
            return False
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        try:
            if not self.login():
                return None
            
            new_uuid = str(uuid.uuid4())
            subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
            expiry_time = int((time.time() + (days * 86400)) * 1000)
            client_email = f"KENT_{device_name}_{user_id}_{int(time.time())}"
            
            print(f"📝 Добавляем: {client_email}, {days} дней")
            
            # Получаем текущий инбоунд
            get_url = f"{self.host}/panel/api/inbounds/get/{self.inbound_id}"
            print(f"🔍 GET: {get_url}")
            
            response = self.session.get(get_url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Статус {response.status_code}")
                return None
            
            try:
                inbound_data = response.json()
            except:
                print(f"❌ Не JSON: {response.text[:100]}")
                return None
            
            if not inbound_data.get('success'):
                print(f"❌ Инбоунд не найден")
                return None
            
            # Получаем клиентов
            current_settings = json.loads(inbound_data['obj']['settings'])
            current_clients = current_settings.get('clients', [])
            
            # Добавляем нового
            new_client = {
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
            current_clients.append(new_client)
            current_settings['clients'] = current_clients
            
            # Обновляем
            update_payload = {
                "id": self.inbound_id,
                "settings": json.dumps(current_settings)
            }
            
            update_url = f"{self.host}/panel/api/inbounds/update/{self.inbound_id}"
            print(f"🔄 PUT: {update_url}")
            
            update_response = self.session.put(update_url, json=update_payload, timeout=10)
            
            if update_response.status_code != 200:
                print(f"❌ Статус {update_response.status_code}")
                return None
            
            try:
                update_result = update_response.json()
            except:
                print(f"⚠️ Ответ не JSON, но возможно успех")
                # Пробуем перезапустить всё равно
                restart_url = f"{self.host}/panel/api/inbounds/restart/{self.inbound_id}"
                self.session.post(restart_url, timeout=10)
                return subscription_id
            
            if update_result.get('success'):
                print(f"✅ Обновлено, перезапускаем...")
                restart_url = f"{self.host}/panel/api/inbounds/restart/{self.inbound_id}"
                self.session.post(restart_url, timeout=10)
                return subscription_id
            else:
                print(f"❌ Ошибка: {update_result}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            return None

    def remove_client(self, email):
        """Удаление клиента"""
        if not self.login():
            return False
        
        get_url = f"{self.host}/panel/api/inbounds/get/{self.inbound_id}"
        try:
            response = self.session.get(get_url, timeout=10)
            inbound_data = response.json()
            
            if not inbound_data.get('success'):
                return False
            
            current_settings = json.loads(inbound_data['obj']['settings'])
            current_clients = current_settings.get('clients', [])
            
            new_clients = [c for c in current_clients if c.get('email') != email]
            
            if len(new_clients) == len(current_clients):
                return False
            
            current_settings['clients'] = new_clients
            
            update_payload = {
                "id": self.inbound_id,
                "settings": json.dumps(current_settings)
            }
            
            update_url = f"{self.host}/panel/api/inbounds/update/{self.inbound_id}"
            update_response = self.session.put(update_url, json=update_payload, timeout=10)
            
            if update_response.json().get('success'):
                restart_url = f"{self.host}/panel/api/inbounds/restart/{self.inbound_id}"
                self.session.post(restart_url, timeout=10)
                return True
            
            return False
            
        except Exception as e:
            print(f"Ошибка: {e}")
            return False