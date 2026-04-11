import requests
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

class XUI:
    def __init__(self):
        self.url = os.getenv("PANEL_URL")
        self.session = requests.Session()
        self.login()

    def login(self):
        self.session.post(f"{self.url}/login", data={
            'username': os.getenv("PANEL_LOGIN"),
            'password': os.getenv("PANEL_PASSWORD")
        })

    def add_client(self, user_id, device_name):
        new_uuid = str(uuid.uuid4())
        client_data = {
            "id": int(os.getenv("INBOUND_ID")),
            "settings": '{"clients": [{"id": "' + new_uuid + '", "alterId": 0, "email": "' + f"{user_id}_{device_name}" + '", "limitIp": 5, "totalGB": 0, "expiryTime": 0, "enable": True}]}'
        }
        r = self.session.post(f"{self.url}/panel/inbound/addClient", data=client_data)
        return new_uuid if r.status_code == 200 else None
