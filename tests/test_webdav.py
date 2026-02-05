import unittest
import requests
import json
import os
import sys
import time
from threading import Thread

# Setup PYTHONPATH
REPO_ROOT = os.path.dirname(os.path.abspath(os.getcwd()))
sys.path.append(os.path.join(REPO_ROOT, "proxion-keyring"))

from proxion_keyring.pod_proxy import PodProxyServer
from proxion_keyring.manager import KeyringManager

class TestWebDAVIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temp stash for testing
        cls.stash_root = os.path.abspath("test_stash_dav")
        os.makedirs(cls.stash_root, exist_ok=True)
        with open(os.path.join(cls.stash_root, "dav_test.txt"), "w") as f: f.write("webdav works")

        # Setup Manager
        cls.manager = KeyringManager()
        cls.manager.pod_local_root = cls.stash_root
        
        # Start Proxy Server
        cls.port = 18099
        cls.server = PodProxyServer(cls.manager)
        cls.server_thread = Thread(target=cls.server.run, args=(cls.port,), daemon=True)
        cls.server_thread.start()
        time.sleep(3)

    def test_01_propfind_root(self):
        """Verify PROPFIND on WebDAV root."""
        url = f"http://127.0.0.1:{self.port}/dav/"
        # PROPFIND is the standard WebDAV method for directory listing
        resp = requests.request("PROPFIND", url, headers={"Depth": "1"})
        self.assertEqual(resp.status_code, 207) # Multi-Status
        self.assertIn("stash", resp.text)
        self.assertIn("cloud", resp.text)

    def test_02_get_file(self):
        """Verify GET on a file via WebDAV."""
        url = f"http://127.0.0.1:{self.port}/dav/stash/dav_test.txt"
        resp = requests.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "webdav works")

if __name__ == '__main__':
    unittest.main()
