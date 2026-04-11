import requests
import os
import uuid
import json
import time
from dotenv import load_dotenv

load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()

    def login(self):
        try:
            url = f"{self.host}/login"
            data = {"username": self.username, "password": self.password}
            # verify=False нужен, так как на IP обычно нет SSL-сертификата
            response = self.session.post(url, data=data, timeout=10, verify=False)
            return response.json().get("success", False)
        except Exception as e:
            print(f"[XUI Error] Login failed: {e}")
            return False

    def add_client(self, user_id, device_name, days=30):
        if not self.login():
            return None
            
        new_uuid = str(uuid.uuid4())
        # Рассчитываем время удаления (текущее время + дни в мс)
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        
        client_dict = {
            "id": new_uuid,
            "flow": "",
            "email": f"{user_id}_{device_name}_{int(time.time())}",
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
            if res_data.get("success"):
                return new_uuid
            print(f"[XUI Error] Panel rejected: {res_data}")
            return None
        except Exception as e:
            print(f"[XUI Error] Request failed: {e}")
            return None
