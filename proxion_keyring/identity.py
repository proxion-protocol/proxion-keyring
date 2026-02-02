import secrets
import threading
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

def load_or_create_identity_key(key_path="identity_private.pem"):
    """
    Load Ed25519 identity key from disk or create a new one.
    This ensures the CLI and Server use the same identity.
    """
    if os.path.exists(key_path):
        try:
            with open(key_path, "rb") as f:
                return serialization.load_pem_private_key(
                    f.read(),
                    password=None
                )
        except Exception as e:
            print(f"Warning: Failed to load identity key: {e}. Generating new one.")
    
    # Generate new
    key = ed25519.Ed25519PrivateKey.generate()
    # Save
    try:
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
    except Exception as e:
        print(f"Warning: Failed to save identity key: {e}")
        
    return key

def derive_child_key(master_key: ed25519.Ed25519PrivateKey, context: str) -> ed25519.Ed25519PrivateKey:
    """
    Derive a deterministic child key for a specific context (Unlinkability).
    Uses HKDF-SHA256.
    """
    # Get raw 32-byte seed from master key
    raw_bytes = master_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=context.encode(),
    )
    derived_bytes = hkdf.derive(raw_bytes)
    return ed25519.Ed25519PrivateKey.from_private_bytes(derived_bytes)

def derive_app_password(master_key: ed25519.Ed25519PrivateKey, app_name: str) -> str:
    """
    Derive a deterministic 16-char password for an app (e.g. adguard).
    Uses HKDF-SHA256 of the master key seed.
    """
    raw_bytes = master_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=16,
        salt=None,
        info=f"app:password:{app_name}".encode(),
    )
    derived = hkdf.derive(raw_bytes)
    # Hex for easy typing if needed, but we typically use it only in the backend.
    return derived.hex()[:16]

class IdentityGateway:
    """
    Handles the "Physical Key" Handshake and Action Confirmations.
    Phase 5 compliance: Zero-Trust authorization.
    """
    
    def __init__(self, manager):
        self.manager = manager
        self.pending_handshakes: Dict[str, dict] = {}
        self.pending_intents: Dict[str, dict] = {} # action_id -> {action, params, status}
        self._lock = threading.Lock()

    # --- Handshake Logic ---

    def create_handshake(self, client_type: str = "extension") -> str:
        """Create a new ephemeral handshake ID."""
        handshake_id = secrets.token_urlsafe(16)
        with self._lock:
            self.pending_handshakes[handshake_id] = {
                "client_type": client_type,
                "payload": None,
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
                "authorized": False
            }
        return handshake_id

    def authorize_handshake(self, handshake_id: str, payload: dict) -> bool:
        """Authorize a pending handshake with a payload (token, webId, etc)."""
        with self._lock:
            if handshake_id not in self.pending_handshakes:
                return False
            
            hs = self.pending_handshakes[handshake_id]
            if datetime.now(timezone.utc) > hs["exp"]:
                del self.pending_handshakes[handshake_id]
                return False
            
            hs["payload"] = payload
            hs["authorized"] = True
            return True

    def poll_handshake(self, handshake_id: str) -> Optional[dict]:
        """Check if a handshake has been authorized."""
        with self._lock:
            if handshake_id not in self.pending_handshakes:
                return None
            
            hs = self.pending_handshakes[handshake_id]
            if hs["authorized"]:
                payload = hs["payload"]
                # Handshake consumed
                del self.pending_handshakes[handshake_id]
                return payload
        return None

    # --- Intent Logic (Action Confirmations) ---
    
    def create_intent(self, action: str, params: dict, requester: str) -> str:
        """Register a pending action that needs mobile confirmation."""
        intent_id = secrets.token_urlsafe(16)
        with self._lock:
            self.pending_intents[intent_id] = {
                "action": action,
                "params": params,
                "requester": requester,
                "status": "pending",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=2)
            }
        return intent_id

    def get_pending_intents(self) -> list:
        """Return all pending intents for the Mobile App to show."""
        now = datetime.now(timezone.utc)
        with self._lock:
            return [
                {"id": k, **v} for k, v in self.pending_intents.items()
                if v["status"] == "pending" and now < v["exp"]
            ]

    def resolve_intent(self, intent_id: str, approved: bool) -> bool:
        """Mobile App approves or denies the action."""
        with self._lock:
            if intent_id not in self.pending_intents:
                return False
            
            intent = self.pending_intents[intent_id]
            intent["status"] = "approved" if approved else "denied"
            return True

    def check_intent(self, intent_id: str) -> str:
        """requester polls for resolution."""
        with self._lock:
            if intent_id not in self.pending_intents:
                return "expired"
            
            status = self.pending_intents[intent_id]["status"]
            if status != "pending":
                # Clean up resolved intent after check
                # We can't delete immediately if multiple components need the result,
                # but for simplicity we assume one caller polls.
                res = self.pending_intents[intent_id]
                del self.pending_intents[intent_id]
                return status
        return "pending"

    def cleanup(self):
        """Purge expired handshakes and intents."""
        now = datetime.now(timezone.utc)
        with self._lock:
            expired_h = [k for k, v in self.pending_handshakes.items() if now > v["exp"]]
            for k in expired_h: del self.pending_handshakes[k]
            
            expired_i = [k for k, v in self.pending_intents.items() if now > v["exp"]]
            for k in expired_i: del self.pending_intents[k]
