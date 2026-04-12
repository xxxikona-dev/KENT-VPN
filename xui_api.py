import requests
import os
import uuid
import json
import time
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.sni = os.getenv("REALITY_SNI", "www.oracle.com")
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def login(self):
        try:
            url = f"{self.host}/login"
            response = self.session.post(url, data={"username": self.username, "password": self.password}, timeout=10, verify=False)
            return response.json().get("success", False)
        except: return False

    def add_client(self, user_id, device_name, days=30):
        if not self.login(): return None
        
        new_uuid = str(uuid.uuid4())
        subscription_id = str(uuid.uuid4()).replace('-', '')[:16]
        expiry_time = int((time.time() + (days * 86400)) * 1000)
        
        # Формируем имя клиента, которое будет видно в списке
        client_email = f"UK_{device_name}_{user_id}"
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        client_dict = {
            "id": new_uuid,
            "flow": "xtls-rprx-vision",
            "email": client_email,
            "limitIp": 2,
            "expiryTime": expiry_time,
            "enable": True,
            "subId": subscription_id,
            "tgId": str(user_id)
        }
        
        payload = {"id": self.inbound_id, "settings": json.dumps({"clients": [client_dict]})}
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            if response.json().get("success"):
                return subscription_id
            return None
        except: return None
