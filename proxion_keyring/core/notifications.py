import os
import json
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec

class NotificationManager:
    """Sovereign Push Notification Hub using VAPID and WebPush."""
    
    def __init__(self, manager):
        self.manager = manager
        self.vault = self.manager.vault
        self.subscriptions_path = os.path.join(self.manager.pod_local_root, "settings", "push_subscriptions.json")

    def ensure_vapid_keys(self):
        """Ensure VAPID keys exist in the Vault, generating them if necessary."""
        vault_path = self.manager.pod_local_root
        keys = self.vault.secure_load(vault_path, "vapid_keys.json")
        if not keys:
            print("RS: Generating new VAPID V3 Keys...")
            # Generate P-256 EC key
            pk = ec.generate_private_key(ec.SECP256R1())
            
            # Export PKCS8 Private Key
            priv_bytes = pk.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Export Uncompressed Public Key (65 bytes)
            pub_bytes = pk.public_key().public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )
            
            def b64url(data): return base64.urlsafe_b64encode(data).decode().rstrip('=')
            
            keys = {
                "private_key": b64url(priv_bytes),
                "public_key": b64url(pub_bytes)
            }
            self.vault.secure_save(vault_path, "vapid_keys.json", keys)
        return keys

    def register_subscription(self, subscription: dict):
        """Add a new WebPush subscription to the Pod."""
        os.makedirs(os.path.dirname(self.subscriptions_path), exist_ok=True)
        
        subs = []
        if os.path.exists(self.subscriptions_path):
            with open(self.subscriptions_path, "r") as f:
                subs = json.load(f)
        
        # Avoid duplicates
        if subscription not in subs:
            subs.append(subscription)
            with open(self.subscriptions_path, "w") as f:
                json.dump(subs, f, indent=2)
            
            self.manager.log_event(
                action="REGISTER PUSH",
                resource="System/Notifications",
                subject="Mobile Client",
                type="success"
            )
        return True

    def get_public_key(self):
        """Return the VAPID applicationServerKey for the frontend."""
        keys = self.ensure_vapid_keys()
        return keys["public_key"]

    def send_broadcast(self, title: str, message: str):
        """Broadcast a notification to all registered Mesh peers (Mock for Phase 5.6)."""
        print(f"RS PUSH BROADCAST: {title} - {message}")
        # In Phase 6, this would iterate through subs and use pywebpush
        return True
