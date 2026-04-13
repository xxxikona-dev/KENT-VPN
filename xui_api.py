import requests
import os
import uuid
import json
import time
import urllib3
import random
import string
import logging
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        self.host = os.getenv("PANEL_URL", "").strip().rstrip('/')
        self.username = os.getenv("PANEL_LOGIN")
        self.password = os.getenv("PANEL_PASSWORD")
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()

    def login(self):
        try:
            url = f"{self.host}/login"
            res = self.session.post(url, data={"username": self.username, "password": self.password}, timeout=10, verify=False)
            return res.json().get("success", False)
        except Exception as e:
            logging.error(f"XUI Login Error: {e}")
            return False

    def add_client(self, user_id, days=30):
        if not self.login(): return None
        
        client_uuid = str(uuid.uuid4())
        sub_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        expiry = int((time.time() + (int(days) * 86400)) * 1000)
        
        # Красивое отображение в панели
        display_email = (" " * 40) + f"kent_{str(user_id)[:5]}"
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        client_data = {
            "id": client_uuid,
            "email": display_email,
            "limitIp": 2,
            "totalGB": 0,
            "expiryTime": expiry,
            "enable": True,
            "tgId": str(user_id),
            "subId": sub_id
        }
        
        payload = {
            "id": self.inbound_id,
            "settings": json.dumps({"clients": [client_data]})
        }
        
        try:
            res = self.session.post(url, json=payload, timeout=10, verify=False)
            if res.json().get("success"):
                return sub_id
            return None
        except Exception as e:
            logging.error(f"XUI Add Client Error: {e}")
            return None
