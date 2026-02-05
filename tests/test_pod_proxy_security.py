
import os
import shutil
import unittest
import threading
import time
import requests
import json
from cryptography.hazmat.primitives.asymmetric import ed25519
import proxion_keyring
print(f"DEBUG: Importing proxion_keyring from {proxion_keyring.__file__}")
from proxion_keyring.pod_proxy import PodProxyServer
from proxion_keyring.manager import KeyringManager

class TestPodProxySecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_root = os.path.abspath("test_security_root")
        if os.path.exists(cls.test_root):
            shutil.rmtree(cls.test_root)
        os.makedirs(cls.test_root)
        os.makedirs(os.path.join(cls.test_root, "photos"))
        os.makedirs(os.path.join(cls.test_root, "private"))

        cls.manager = KeyringManager()
        cls.manager.pod_local_root = cls.test_root
        cls.server = PodProxyServer(cls.manager)
        
        cls.server_thread = threading.Thread(target=cls.server.run, kwargs={"port": 8091})
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(1)

        # Generate test session key
        cls.session_key = ed25519.Ed25519PrivateKey.generate()
        from cryptography.hazmat.primitives import serialization
        cls.session_pub_hex = cls.session_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

    def _get_dpop(self, method, path):
        payload = f"{method}:{path}"
        sig = self.session_key.sign(payload.encode())
        return json.dumps({
            "method": method,
            "path": path,
            "signature": sig.hex(),
            "pubkey": self.session_pub_hex
        })

    def test_01_unauthorized_fail(self):
        resp = requests.get("http://127.0.0.1:8091/pod/")
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Missing or invalid Authorization", resp.json()["error"])

    def test_02_login_and_access(self):
        # 1. Login
        resp = requests.post("http://127.0.0.1:8091/auth/stash_login", json={"pubkey": self.session_pub_hex})
        self.assertEqual(resp.status_code, 200)
        token = resp.json()

        # 2. Access with token and DPoP
        headers = {
            "Authorization": f"Bearer {json.dumps(token)}",
            "DPoP": self._get_dpop("GET", "/"),
            "Accept": "application/json"
        }
        resp = requests.get("http://127.0.0.1:8091/pod/", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("entries", resp.json())

    def test_03_attenuation_enforced(self):
        # 1. Mint attenuated token for /photos only
        token = self.manager.mint_stash_token(self.session_pub_hex, path_prefix="/photos")
        
        # 2. Access /photos (Allowed)
        headers = {
            "Authorization": f"Bearer {json.dumps(token)}",
            "DPoP": self._get_dpop("GET", "/photos"),
            "Accept": "application/json"
        }
        resp = requests.get("http://127.0.0.1:8091/pod/photos", headers=headers)
        self.assertEqual(resp.status_code, 200)

        # 3. Access /private (Forbidden by Caveat)
        headers["DPoP"] = self._get_dpop("GET", "/private")
        resp = requests.get("http://127.0.0.1:8091/pod/private", headers=headers)
        self.assertEqual(resp.status_code, 403)
        self.assertIn("Unauthorized", resp.json()["error"])

    def test_04_tampered_signature_fail(self):
        resp = requests.post("http://127.0.0.1:8091/auth/stash_login", json={"pubkey": self.session_pub_hex})
        token = resp.json()
        token["signature"] = "tampered"

        headers = {
            "Authorization": f"Bearer {json.dumps(token)}",
            "DPoP": self._get_dpop("GET", "/"),
            "Accept": "application/json"
        }
        resp = requests.get("http://127.0.0.1:8091/pod/", headers=headers)
        self.assertEqual(resp.status_code, 403)

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_root):
            shutil.rmtree(cls.test_root)

if __name__ == "__main__":
    unittest.main()
