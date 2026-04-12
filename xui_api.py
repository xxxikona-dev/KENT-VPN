import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

# Отключаем проверку SSL, так как на панели может быть самоподписанный сертификат
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()
        # Важно для работы через HTTPS
        self.session.verify = False 
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        try:
            url = f"{self.host}/login"
            response = self.session.post(
                url, 
                data={"username": self.username, "password": self.password}, 
                timeout=10
            )
            # Проверяем статус ответа
            if response.status_code != 200:
                print(f"Ошибка логина: Статус {response.status_code}")
                return False
            result = response.json()
            return result.get("success", False)
        except Exception as e:
            print(f"Критическая ошибка логина: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        try:
            if not self.login():
                print("Не удалось авторизоваться в панели для добавления клиента")
                return None
            
            new_uuid = str(uuid.uuid4())
            subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
            expiry_time = int((time.time() + (days * 86400)) * 1000)
            # Добавляем timestamp чтобы избежать дубликатов
            client_email = f"KENT_{device_name}_{user_id}_{int(time.time())}"
            
            print(f"Добавляем клиента: {client_email}, дней: {days}")
            
            # Получаем текущий инбоунд
            get_url = f"{self.host}/panel/api/inbounds/get/{self.inbound_id}"
            response = self.session.get(get_url, timeout=10)
            inbound_data = response.json()
            
            if not inbound_data.get('success'):
                print(f"Не удалось получить инбоунд: {inbound_data}")
                return None
            
            # Получаем текущих клиентов
            current_settings = json.loads(inbound_data['obj']['settings'])
            current_clients = current_settings.get('clients', [])
            
            # Добавляем нового клиента
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
            
            # Обновляем настройки
            current_settings['clients'] = current_clients
            
            # Отправляем обновление
            update_payload = {
                "id": self.inbound_id,
                "settings": json.dumps(current_settings)
            }
            
            update_url = f"{self.host}/panel/api/inbounds/update/{self.inbound_id}"
            update_response = self.session.put(update_url, json=update_payload, timeout=10)
            update_result = update_response.json()
            
            if update_result.get('success'):
                print(f"Инбоунд обновлён, перезапускаем...")
                # Перезапускаем инбоунд
                restart_url = f"{self.host}/panel/api/inbounds/restart/{self.inbound_id}"
                restart_response = self.session.post(restart_url, timeout=10)
                
                if restart_response.json().get('success'):
                    print(f"✅ Клиент {client_email} успешно добавлен")
                    return subscription_id
                else:
                    print(f"❌ Не удалось перезапустить инбоунд")
                    return None
            else:
                print(f"❌ Не удалось обновить инбоунд: {update_result}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка при добавлении клиента: {e}")
            import traceback
            traceback.print_exc()
            return None

    def remove_client(self, email):
        """Удаление клиента по email"""
        if not self.login():
            print("Не удалось авторизоваться для удаления клиента")
            return False
        
        get_url = f"{self.host}/panel/api/inbounds/get/{self.inbound_id}"
        try:
            response = self.session.get(get_url, timeout=10)
            inbound_data = response.json()
            
            if not inbound_data.get('success'):
                return False
            
            current_settings = json.loads(inbound_data['obj']['settings'])
            current_clients = current_settings.get('clients', [])
            
            # Фильтруем клиентов, оставляя всех кроме того, кого нужно удалить
            new_clients = [client for client in current_clients if client.get('email') != email]
            
            if len(new_clients) == len(current_clients):
                print(f"Клиент с email {email} не найден")
                return False
            
            # Обновляем настройки
            current_settings['clients'] = new_clients
            
            update_payload = {
                "id": self.inbound_id,
                "settings": json.dumps(current_settings)
            }
            
            update_url = f"{self.host}/panel/api/inbounds/update/{self.inbound_id}"
            update_response = self.session.put(update_url, json=update_payload, timeout=10)
            
            if update_response.json().get('success'):
                # Перезапускаем инбоунд
                restart_url = f"{self.host}/panel/api/inbounds/restart/{self.inbound_id}"
                self.session.post(restart_url, timeout=10)
                return True
            
            return False
            
        except Exception as e:
            print(f"Ошибка при удалении клиента: {e}")
            return False

    def get_clients(self):
        """Получение списка всех клиентов"""
        if not self.login():
            print("Не удалось авторизоваться для получения списка клиентов")
            return []
        
        get_url = f"{self.host}/panel/api/inbounds/get/{self.inbound_id}"
        try:
            response = self.session.get(get_url, timeout=10)
            inbound_data = response.json()
            
            if not inbound_data.get('success'):
                return []
            
            current_settings = json.loads(inbound_data['obj']['settings'])
            return current_settings.get('clients', [])
            
        except Exception as e:
            print(f"Ошибка при получении списка клиентов: {e}")
            return []