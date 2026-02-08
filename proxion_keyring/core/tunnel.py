import os
import json
import time
from typing import Dict, Optional, Any
from datetime import datetime, timezone

class Tunnel:
    """WireGuard and Mobile Onboarding management."""
    
    def __init__(self, pod_local_root: str, backend):
        self.pod_local_root = pod_local_root
        self.backend = backend
        self.peers_path = os.path.join(self.pod_local_root, "peers.json")
        self.invites_path = os.path.join(self.pod_local_root, "invitations.json")
        
        self.registered_peers: Dict[str, Dict] = self._load_peers()
        self.invitations: Dict[str, Dict] = self._load_invitations()
        self.rate_limits: Dict[str, list] = {} # ip -> [timestamps]

        self.wg_server_priv: Optional[str] = None
        self.wg_server_pub: Optional[str] = None
        self._ensure_wireguard_keys()

    def _ensure_wireguard_keys(self):
        """Ensure persistent WireGuard identity exists."""
        key_file = os.path.join(self.pod_local_root, "wg_server.key")
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                self.wg_server_priv = f.read().strip()
        else:
            # Generate new keypair via backend
            if hasattr(self.backend, "generate_keypair"):
                self.wg_server_priv, _ = self.backend.generate_keypair()
            else:
                # Fallback / Mock
                self.wg_server_priv = "DUMMY_PRIVATE_KEY"
                
            with open(key_file, "w") as f:
                f.write(self.wg_server_priv)
        
        if hasattr(self.backend, "get_public_from_private"):
            self.wg_server_pub = self.backend.get_public_from_private(self.wg_server_priv)
        else:
            self.wg_server_pub = "DUMMY_PUBLIC_KEY"

    def register_mobile_peer(self, pubkey: str, metadata: Dict[str, Any]):
        """Track a registered device for revocation."""
        self.registered_peers[pubkey] = {
            "registered_at": datetime.now(timezone.utc).isoformat(),
            **metadata
        }
        self._save_peers()

    def revoke_peer(self, pubkey: str):
        """Kill switch for a specific mobile peer."""
        if pubkey in self.registered_peers:
            del self.registered_peers[pubkey]
            self._save_peers()
            # Actual WireGuard removal logic would go here
            return True
        return False

    def _save_peers(self):
        try:
            with open(self.peers_path, "w") as f:
                json.dump(self.registered_peers, f, indent=2)
        except Exception as e:
            print(f"Tunnel: Failed to save peers: {e}")

    def _load_peers(self):
        if os.path.exists(self.peers_path):
            try:
                with open(self.peers_path, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def _load_invitations(self):
        if os.path.exists(self.invites_path):
            try:
                with open(self.invites_path, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def _save_invitations(self):
        try:
            with open(self.invites_path, "w") as f:
                json.dump(self.invitations, f, indent=2)
        except Exception as e:
            print(f"Tunnel: Failed to save invitations: {e}")

    def create_invitation(self, capabilities: list, expiration_delta: str, metadata: dict):
        import uuid
        invite_id = str(uuid.uuid4())
        self.invitations[invite_id] = {
            "capabilities": capabilities,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata,
            "used": False
        }
        self._save_invitations()
        return invite_id

    def check_rate_limit(self, client_ip: str) -> bool:
        now = time.time()
        timestamps = self.rate_limits.get(client_ip, [])
        # Cleanup old
        timestamps = [t for t in timestamps if now - t < 3600]
        if len(timestamps) >= 5:
            return False
        timestamps.append(now)
        self.rate_limits[client_ip] = timestamps
        return True
