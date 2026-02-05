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

class TestPodProxyAux(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a temp stash for testing
        cls.stash_root = os.path.abspath("test_stash_aux")
        os.makedirs(cls.stash_root, exist_ok=True)
        
        # Create files and sidecars
        with open(os.path.join(cls.stash_root, "file.txt"), "w") as f: f.write("content")
        with open(os.path.join(cls.stash_root, "file.txt.acl"), "w") as f: f.write("acl")
        os.makedirs(os.path.join(cls.stash_root, "subdir"), exist_ok=True)
        with open(os.path.join(cls.stash_root, "subdir.acl"), "w") as f: f.write("subdir acl")

        # Setup Manager
        cls.manager = KeyringManager()
        cls.manager.pod_local_root = cls.stash_root
        
        # Start Proxy Server
        cls.server = PodProxyServer(cls.manager)
        cls.server_thread = Thread(target=cls.server.run, args=(8094,), daemon=True)
        cls.server_thread.start()
        time.sleep(2)

        # Setup Client
        cls.client = PodClient("http://localhost:8094")

    def test_01_link_headers_file(self):
        """Verify Link headers for a regular file."""
        headers = {
            "Authorization": f"Bearer {json.dumps(self.client.token)}",
            "DPoP": self.client._sign_request("GET", "/file.txt"),
            "Accept": "application/json"
        }
        resp = requests.get("http://localhost:8094/pod/file.txt", headers=headers)
        self.assertEqual(resp.status_code, 200)
        links = resp.headers.get("Link", "")
        self.assertIn('<file.txt.acl>; rel="acl"', links)
        self.assertIn('<file.txt.meta>; rel="describedby"', links)

    def test_02_link_headers_dir(self):
        """Verify Link headers for a directory."""
        headers = {
            "Authorization": f"Bearer {json.dumps(self.client.token)}",
            "DPoP": self.client._sign_request("GET", "/subdir"),
            "Accept": "application/json"
        }
        resp = requests.get("http://localhost:8094/pod/subdir", headers=headers)
        self.assertEqual(resp.status_code, 200)
        links = resp.headers.get("Link", "")
        # Rel: <subdir.acl>; rel="acl" (based on our base_name logic)
        self.assertIn('<subdir.acl>; rel="acl"', links)
        self.assertIn('http://www.w3.org/ns/ldp#BasicContainer', links)

    def test_03_hidden_sidecars(self):
        """Verify sidecars are hidden from readdir."""
        entries = self.client.list_dir("/")
        self.assertIn("file.txt", entries)
        self.assertIn("subdir", entries)
        self.assertNotIn("file.txt.acl", entries)
        self.assertNotIn("subdir.acl", entries)

    def test_04_cleanup_axiom(self):
        """Verify Solid Cleanup Axiom (automatic sidecar deletion)."""
        # Delete file.txt
        headers = {
            "Authorization": f"Bearer {json.dumps(self.client.token)}",
            "DPoP": self.client._sign_request("DELETE", "/file.txt")
        }
        resp = requests.delete("http://localhost:8094/pod/file.txt", headers=headers)
        self.assertEqual(resp.status_code, 204)
        
        # Verify both main and sidecar are gone
        self.assertFalse(os.path.exists(os.path.join(self.stash_root, "file.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.stash_root, "file.txt.acl")))

if __name__ == '__main__':
    unittest.main()
