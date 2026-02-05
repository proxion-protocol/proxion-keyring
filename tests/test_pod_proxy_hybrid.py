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
sys.path.append(os.path.join(REPO_ROOT, "proxion-fuse"))

from proxion_keyring.pod_proxy import PodProxyServer
from proxion_keyring.manager import KeyringManager
from mount import PodClient

class TestPodProxyHybrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temp stash for testing
        cls.stash_root = os.path.abspath("test_stash_hybrid")
        os.makedirs(cls.stash_root, exist_ok=True)
        with open(os.path.join(cls.stash_root, "local.txt"), "w") as f: f.write("local content")

        # Setup Manager
        cls.manager = KeyringManager()
        cls.manager.pod_local_root = cls.stash_root
        
        # Start Proxy Server on a high random port
        cls.port = 18095
        cls.server = PodProxyServer(cls.manager)
        cls.server_thread = Thread(target=cls.server.run, args=(cls.port,), daemon=True)
        cls.server_thread.start()
        time.sleep(3)

        # Setup Client pointing to 127.0.0.1
        cls.client = PodClient(f"http://127.0.0.1:{cls.port}")

    def test_01_root_listing(self):
        """Verify the unified root lists all providers."""
        entries = self.client.list_dir("/")
        self.assertIn("stash", entries)
        self.assertIn("cloud", entries)

    def test_02_local_routing(self):
        """Verify routing to local provider works."""
        entries = self.client.list_dir("/stash")
        self.assertIn("local.txt", entries)

    def test_03_remote_routing(self):
        """Verify routing to mock remote provider works."""
        entries = self.client.list_dir("/cloud")
        self.assertIn("cloud_data.txt", entries)

    def test_04_remote_data_fetch(self):
        """Verify fetching data from mock remote provider."""
        # Note: we need to use a valid token and signature
        if not self.client.token:
            self.skipTest("No token available")
            
        headers = {
            "Authorization": f"Bearer {json.dumps(self.client.token)}",
            "DPoP": self.client._sign_request("GET", "/cloud/cloud_data.txt")
        }
        resp = requests.get(f"http://127.0.0.1:{self.port}/pod/cloud/cloud_data.txt", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"virtual remote resource", resp.content)

if __name__ == '__main__':
    unittest.main()
