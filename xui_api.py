import requests
import os
import uuid
import json
import time
import urllib3
import random
import string
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

class XUI:
    def __init__(self):
        # Оставляем только чистые IP
        self.ips = ["91.199.32.144"]
        self.login_user = os.getenv("PANEL_LOGIN")
        self.login_pass = os.getenv("PANEL_PASSWORD")
        # Порт для работы API остается 2096 (или какой у тебя стоит для входа в панель)
        self.api_port = "2096" 
        self.inbound_id = int(os.getenv("INBOUND_ID", 3))
        self.session = requests.Session()

    def login_to_srv(self, ip):
        try:
            url = f"https://{ip}:{self.api_port}/login"
            res = self.session.post(
                url, 
                data={"username": self.login_user, "password": self.login_pass}, 
                timeout=5, 
                verify=False
            )
            return res.json().get("success", False)
        except:
            return False

    def add_client(self, user_id, days=30):
        common_uuid = str(uuid.uuid4())
        # Это ID, который пойдет в ссылку после /sub/
        common_sub_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        expiry_time = int((time.time() + (int(days) * 86400)) * 1000)
        
        success_count = 0
        for ip in self.ips:
            if not self.login_to_srv(ip): continue
            
            display_email = (" " * 50) + "happ_" + str(user_id)[:4]
            url = f"https://{ip}:{self.api_port}/panel/api/inbounds/addClient"
            
            client_dict = {
                "id": common_uuid,
                "email": display_email,
                "limitIp": 2,
                "totalGB": 0,
                "expiryTime": expiry_time,
                "enable": True,
                "tgId": str(user_id),
                "subId": common_sub_id
            }
            
            payload = {"id": self.inbound_id, "settings": json.dumps({"clients": [client_dict]})}
            try:
                res = self.session.post(url, json=payload, timeout=5, verify=False)
                if res.json().get("success"): success_count += 1
            except: continue
            
        return common_sub_id if success_count > 0 else None
