import os
import threading
from typing import Dict, Optional, Any
from datetime import datetime, timezone
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

class KeyringManager:
    """
    Central coordinator for Proxion Keyring state.
    Handles Solid sessions, WireGuard tunnels, and Spec-compliant cryptography (PoP).
    """
    
    def __init__(self):
        # Warden Perimeter Security
        from .warden import Warden
        self.warden = Warden()

        # Lens Unified Search
        from .lens import Lens
        self.lens = Lens(self)
        self.lens.refresh_index()

        # Archivist Memory Keeper
        from .archivist import Archivist
        self.archivist = Archivist(self)

        # Identity Gateway (Physical Key Handshake)
        from .identity import IdentityGateway
        self.gateway = IdentityGateway(self)

        # Mesh Coordinator (Group LANs)
        from .mesh import MeshCoordinator
        self.mesh = MeshCoordinator(self)

        self.sessions: Dict[str, Any] = {}  # Active sessions
        self.tunnels: Dict[str, str] = {}   # tunnel_id -> peer_ip
        self.metadata_cache: Dict[str, Any] = {}
        from proxion_core import RevocationList
        self.revocation_list = RevocationList()
        self.registered_peers: Dict[str, Dict] = {} # pubkey -> metadata
        
        # Identity for the Keyring itself (The Agent)
        # Persisted securely via helper
        from .identity import load_or_create_identity_key
        self.private_key = load_or_create_identity_key()
        self.public_key = self.private_key.public_key()
        
        self._lock = threading.Lock()
        self._load_peers()

        # WireGuard Server Identity
        from .rs.backends.factory import create_backend
        self.bg_backend = create_backend(use_mock=False) # Use real backend for KeyGen
        self.wg_server_priv: Optional[str] = None
        self.wg_server_pub: Optional[str] = None
        self._ensure_wireguard_keys()

    def _ensure_wireguard_keys(self):
        """Ensure persistent WireGuard identity exists."""
        # Simple file persistence for MVP
        key_path = "wg_private.key"
        if os.path.exists(key_path):
            with open(key_path, "r") as f:
                self.wg_server_priv = f.read().strip()
                try:
                    self.wg_server_pub = self.bg_backend.get_public_from_private(self.wg_server_priv)
                except Exception as e:
                    print(f"Failed to derive pubkey from persisted key: {e}")
                    # Fallback regen
                    pass
        
        if not self.wg_server_priv:
            try:
                self.wg_server_priv, self.wg_server_pub = self.bg_backend.generate_keypair()
                with open(key_path, "w") as f:
                    f.write(self.wg_server_priv)
                print(f"Generated new WireGuard Identity: {self.wg_server_pub[:8]}...")
            except Exception as e:
                print(f"ERROR: Failed to generate WireGuard keys: {e}")
                # Fallback to demo
                self.wg_server_pub = "DEMO_SERVER_PUBKEY"

    def generate_client_config(self) -> Dict[str, str]:
        """Generate a new client identity for Mobile Onboarding."""
        try:
            priv, pub = self.bg_backend.generate_keypair()
            return {
                "private_key": priv,
                "public_key": pub
            }
        except Exception as e:
            print(f"Keygen failed: {e}")
            return {"private_key": "ERROR", "public_key": "ERROR"}

    def register_mobile_peer(self, pubkey: str, metadata: Dict[str, Any]):
        """Track a registered device for revocation."""
        with self._lock:
            self.registered_peers[pubkey] = {
                **metadata,
                "registered_at": datetime.now(timezone.utc).isoformat()
            }
            # Persistence
            self._save_peers()

    def revoke_peer(self, pubkey: str):
        """Zero-Touch Kill Switch."""
        with self._lock:
            if pubkey in self.registered_peers:
                peer_data = self.registered_peers[pubkey]
                token_id = peer_data.get("token_id")
                if token_id:
                    self.revocation_list.revoke(token_id, datetime.now(timezone.utc))
                
                del self.registered_peers[pubkey]
                self._save_peers()
                print(f"Keyring: Revoked peer {pubkey[:8]} and its token.")

    def _save_peers(self):
        import json
        with open("peers.json", "w") as f:
            json.dump(self.registered_peers, f)

    def _load_peers(self):
        import json
        if os.path.exists("peers.json"):
            try:
                with open("peers.json", "r") as f:
                    self.registered_peers = json.load(f)
            except:
                self.registered_peers = {}

    def _save_peers(self):
        import json
        try:
            with open("peers.json", "w") as f:
                json.dump(self.registered_peers, f, indent=2)
        except Exception as e:
            print(f"Failed to save peers: {e}")

    def store_relationship(self, cert_dict: Dict[str, Any]):
        """Store a verified Relationship Certificate."""
        with self._lock:
            # We store by Subject Public Key (Peer ID)
            # One peer might have multiple certs (e.g. distinct capabilities), 
            # but for MVP let's assume one active cert per peer-issuer pair.
            # Storing by cert_id is safer.
            cert_id = cert_dict.get("certificate_id")
            subject = cert_dict.get("subject")
            
            if not cert_id:
                return # Invalid cert
                
            self.registered_peers[cert_id] = {
                "type": "relationship_certificate",
                "received_at": datetime.now(timezone.utc).isoformat(),
                "status": "active",
                "certificate": cert_dict,
                "subject_id": subject
            }
            self._save_peers()

    def get_relationships(self) -> Dict[str, Any]:
        """Return all active relationships."""
        with self._lock:
            return {
                k: v for k, v in self.registered_peers.items() 
                if v.get("image") is None # exclude old metadata-only peers if mixed
                and v.get("type") == "relationship_certificate"
            }

    def revoke_relationship(self, cert_id: str):
        """Revoke a relationship certificate."""
        with self._lock:
            if cert_id in self.registered_peers:
                self.registered_peers[cert_id]["status"] = "revoked"
                self._save_peers()
                # TODO: Trigger WireGuard peer removal
                # cert = self.registered_peers[cert_id]["certificate"]
                # self.bg_backend.remove_peer(cert["wireguard"]["peer_public_key"])

    def get_public_key_hex(self) -> str:
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

    def sign_challenge(self, challenge: bytes) -> bytes:
        """Requirement 3.3: Proof-of-Possession (PoP)"""
        return self.private_key.sign(challenge)

    def register_tunnel(self, tunnel_id: str, peer_ip: str):
        with self._lock:
            self.tunnels[tunnel_id] = peer_ip

    def get_tunnel_ip(self, tunnel_id: str) -> Optional[str]:
        return self.tunnels.get(tunnel_id)

    def activate_session(self, web_id: str, access_token: str):
        """Bridge the session from the frontend."""
        with self._lock:
            self.sessions[web_id] = {
                "access_token": access_token,
                "activated_at": datetime.now(timezone.utc).isoformat()
            }
            print(f"Keyring: Session activated for {web_id}")

    def get_auth_headers(self, url: str, method: str) -> Dict[str, str]:
        """
        Inject Solid OIDC tokens into outgoing requests.
        """
        # For now, use the first active session found. 
        # In a multi-user scenario, we'd look up by context.
        token = "demo-token-placeholder"
        if self.sessions:
            first_webid = next(iter(self.sessions))
            token = self.sessions[first_webid]["access_token"]

        return {
            "Authorization": f"Bearer {token}",
            "X-Proxion-Agent": self.get_public_key_hex()
        }

    def get_pod_url(self) -> str:
        # Mocking for now, usually pulled from authenticated profile
        return os.getenv("PROXION_POD_URL", "https://pod.example.com")
