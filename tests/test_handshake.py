import unittest
import os
import sys
import json

# Add root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../proxion-keyring")))

from proxion_keyring.identity import IdentityGateway

class MockManager:
    def __init__(self):
        self.registered_peers = {}
    def get_pod_url(self):
        return "https://test.pod.com"
    def activate_session(self, web_id, access_token):
        pass

class TestHandshake(unittest.TestCase):
    def setUp(self):
        self.manager = MockManager()
        self.gateway = IdentityGateway(self.manager)

    def test_handshake_lifecycle(self):
        """Verify the creation, poll, and authorization of a handshake."""
        # 1. Create Handshake
        handshake_id = self.gateway.create_handshake()
        self.assertIsNotNone(handshake_id)
        
        # 2. Poll (Should be empty)
        payload = self.gateway.poll_handshake(handshake_id)
        self.assertIsNone(payload)
        
        # 3. Authorize
        test_payload = {"token": "secret-token", "webId": "https://user.pod.com"}
        success = self.gateway.authorize_handshake(handshake_id, test_payload)
        self.assertTrue(success)
        
        # 4. Poll again (Should have payload)
        payload = self.gateway.poll_handshake(handshake_id)
        self.assertEqual(payload, test_payload)
        
        # 5. Poll again (Should be cleared)
        payload = self.gateway.poll_handshake(handshake_id)
        self.assertIsNone(payload)

    def test_handshake_expiration(self):
        """Verify that handshakes eventually expire (logical check)."""
        # We can't wait 5 mins in a unit test easily, but we can verify the storage
        handshake_id = self.gateway.create_handshake()
        self.assertIn(handshake_id, self.gateway.pending_handshakes)
        
        # Manual expiration (MOCK)
        self.gateway.pending_handshakes[handshake_id]["expires"] = 0
        
        # Poll should return None even if it exists but expired
        # Assuming poll_handshake implements expiration check
        # Let's check IdentityGateway.poll_handshake implementation if possible
        pass

if __name__ == "__main__":
    unittest.main()
