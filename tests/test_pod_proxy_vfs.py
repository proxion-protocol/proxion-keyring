
import os
import shutil
import unittest
import threading
import time
import requests
from proxion_keyring.pod_proxy import PodProxyServer
from proxion_keyring.manager import KeyringManager

class TestPodProxyVFS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_root = os.path.abspath("test_pod_root")
        if os.path.exists(cls.test_root):
            shutil.rmtree(cls.test_root)
        os.makedirs(cls.test_root)
        
        # Create a dummy sensitive file
        with open(os.path.join(cls.test_root, "identity_private.pem"), "w") as f:
            f.write("SECRET_KEY")

        cls.manager = KeyringManager()
        cls.manager.pod_local_root = cls.test_root
        cls.server = PodProxyServer(cls.manager)
        
        cls.server_thread = threading.Thread(target=cls.server.run, kwargs={"port": 8090})
        cls.server_thread.daemon = True
        cls.server_thread.start()
        time.sleep(1) # Wait for server to start

    def test_01_root_listing(self):
        resp = requests.get("http://localhost:8090/pod/", headers={"Accept": "application/json"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("entries", data)
        # identity_private.pem should NOT be in the listing
        self.assertNotIn("identity_private.pem", data["entries"])

    def test_02_create_folder(self):
        resp = requests.post("http://localhost:8090/pod/test_folder?type=container")
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(os.path.isdir(os.path.join(self.test_root, "test_folder")))

    def test_03_write_file(self):
        content = b"Hello Proxion"
        resp = requests.put("http://localhost:8090/pod/test_folder/hello.txt", data=content)
        self.assertEqual(resp.status_code, 201)
        
        file_path = os.path.join(self.test_root, "test_folder", "hello.txt")
        self.assertTrue(os.path.exists(file_path))
        with open(file_path, "rb") as f:
            self.assertEqual(f.read(), content)

    def test_04_read_file(self):
        resp = requests.get("http://localhost:8090/pod/test_folder/hello.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"Hello Proxion")

    def test_05_exclusion_list(self):
        # Direct access to excluded file should be forbidden
        resp = requests.get("http://localhost:8090/pod/identity_private.pem")
        self.assertEqual(resp.status_code, 403)
        self.assertIn("restricted", resp.json()["error"])

    def test_06_traversal_protection(self):
        # Attempt to escape root
        resp = requests.get("http://localhost:8090/pod/../outside.txt")
        # Flask/Requests might normalize this, but let's test absolute escape if possible
        # Real traversal prevention is in PodProxyServer._safe_path
        resp = requests.get("http://localhost:8090/pod/%2e%2e/outside.txt")
        self.assertIn(resp.status_code, [403, 404])

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_root):
            shutil.rmtree(cls.test_root)

if __name__ == "__main__":
    unittest.main()
