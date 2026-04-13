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
            response = self.session.post(url, data={"username": self.username, "password": self.password}, timeout=10, verify=False)
            return response.json().get("success", False)
        except Exception as e:
            logging.error(f"Login Error: {e}")
            return False

    def add_client(self, user_id, days=30):
        if not self.login(): return None
        new_uuid = str(uuid.uuid4())
        subscription_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        invisible_padding = " " * 50 
        display_email = f"{invisible_padding}kent_{str(user_id)[:4]}" 
        expiry_time = int((time.time() + (int(days) * 86400)) * 1000)
        
        url = f"{self.host}/panel/api/inbounds/addClient"
        client_dict = {
            "id": new_uuid,
            "email": display_email,
            "limitIp": 2,
            "totalGB": 0,
            "expiryTime": expiry_time,
            "enable": True,
            "tgId": str(user_id),
            "subId": subscription_id
        }
        payload = {"id": self.inbound_id, "settings": json.dumps({"clients": [client_dict]})}
        
        try:
            response = self.session.post(url, json=payload, timeout=10, verify=False)
            if response.json().get("success"):
                return subscription_id
            return None
        except:
            return None
