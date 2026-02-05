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

class TestUXIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temp stash for testing
        cls.stash_root = os.path.abspath("test_stash_ux")
        os.makedirs(cls.stash_root, exist_ok=True)
        with open(os.path.join(cls.stash_root, "searchable.txt"), "w") as f: f.write("find me")

        # Setup Manager
        cls.manager = KeyringManager()
        cls.manager.pod_local_root = cls.stash_root
        
        # Mock Lens MOUNT_POINTS to avoid scanning user drives
        cls.manager.lens.MOUNT_POINTS = {} 
        
        # Start Proxy Server
        cls.port = 18097
        cls.server = PodProxyServer(cls.manager)
        cls.server_thread = Thread(target=cls.server.run, args=(cls.port,), daemon=True)
        cls.server_thread.start()
        time.sleep(3)

        # Setup Client
        cls.client = PodClient(f"http://127.0.0.1:{cls.port}")

    def test_01_sync_status_sidecar(self):
        """Verify virtual .status sidecar returns correct state."""
        headers = {
            "Authorization": f"Bearer {json.dumps(self.client.token)}",
            "DPoP": self.client._sign_request("GET", "/stash/searchable.txt.status")
        }
        # Local file should be 'synced'
        resp = requests.get(f"http://127.0.0.1:{self.port}/pod/stash/searchable.txt.status", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "synced")

        # Cloud file should be 'cloud-only'
        headers["DPoP"] = self.client._sign_request("GET", "/cloud/cloud_data.txt.status")
        resp = requests.get(f"http://127.0.0.1:{self.port}/pod/cloud/cloud_data.txt.status", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.text, "cloud-only")

    def test_02_lens_indexing(self):
        """Verify Lens indexes the pod space."""
        # Force a scan
        self.manager.lens.scan_mounts()
        
        # Verify searchable.txt is in the index
        results = self.manager.lens.search("searchable")
        self.assertTrue(any("searchable.txt" in r["name"] for r in results), f"Results: {results}")
        
        # Verify cloud_data.txt is in the index
        results = self.manager.lens.search("cloud_data")
        self.assertTrue(any("cloud_data.txt" in r["name"] for r in results), f"Results: {results}")

    def test_03_search_endpoint(self):
        """Verify /pod/search returns results via HTTP."""
        resp = requests.get(f"http://127.0.0.1:{self.port}/pod/search?q=searchable")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()
        self.assertTrue(len(results) > 0)
        self.assertIn("searchable.txt", results[0]["name"])

if __name__ == '__main__':
    unittest.main()
