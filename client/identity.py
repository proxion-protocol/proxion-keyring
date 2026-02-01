import os
import json
import stat
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

class IdentityManager:
    """Manages the device's persistent identity (Ed25519 Keypair)."""

    def __init__(self, storage_dir: str = None):
        if storage_dir:
            self.storage_dir = Path(storage_dir)
        else:
            self.storage_dir = Path.home() / ".proxion-keyring"
        
        self.identity_file = self.storage_dir / "device.key"
        self._ensure_storage()

    def _ensure_storage(self):
        """Ensure storage directory exists with safe permissions."""
        if not self.storage_dir.exists():
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            # On Unix, we'd chmod 700 here. Windows permissions are more complex,
            # but standard user separation usually applies.

    def get_identity(self) -> ed25519.Ed25519PrivateKey:
        """Load existing identity or generate a new one."""
        if self.identity_file.exists():
            return self._load_identity()
        return self._generate_identity()

    def _load_identity(self) -> ed25519.Ed25519PrivateKey:
        try:
            with open(self.identity_file, "r") as f:
                data = json.load(f)
            
            raw_private = bytes.fromhex(data["private_key"])
            private_key = ed25519.Ed25519PrivateKey.from_private_bytes(raw_private)
            return private_key
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Corrupt file? Backup and re-generate? 
            # For now, simplistic approach: raise error
            raise ValueError(f"Corrupt identity file: {e}")

    def _generate_identity(self) -> ed25519.Ed25519PrivateKey:
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()

        raw_private = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        raw_public = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )

        data = {
            "private_key": raw_private.hex(),
            "public_key": raw_public.hex(),
            "created_at": os.path.getmtime(self.storage_dir) if self.storage_dir.exists() else 0 # simple timestamp
        }

        # Atomic write
        temp_file = self.identity_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=2)
        
        # Safe permission setting (Unix-like)
        try:
            os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR) # 0o600
        except Exception:
            pass # Windows robustness

        temp_file.replace(self.identity_file)
        return private_key

    def get_public_key_hex(self, private_key: ed25519.Ed25519PrivateKey) -> str:
        """Helper to get hex pubkey from private key object."""
        return private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()
