import os
import json
import base64
import hashlib
import hmac
from typing import Dict, Optional, Tuple
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class VaultManager:
    """
    Manages Zero-Knowledge encryption for Proxion state files.
    Ensures that data stored on the Solid Pod is invisible to the provider.
    """
    
    def __init__(self, master_key: bytes):
        self.master_key = master_key
        # Derivations
        self.vault_key = self._derive_key(b"proxion:vault:v1")
        self.filename_key = self._derive_key(b"proxion:filename_blind:v1")
        self.aead = AESGCM(self.vault_key)

    def _derive_key(self, info: bytes) -> bytes:
        """Derive a specialized key using HKDF."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=info,
        )
        return hkdf.derive(self.master_key)

    def encrypt_data(self, data: Dict) -> bytes:
        """Encrypt JSON data using AES-256-GCM."""
        nonce = os.urandom(12)
        plaintext = json.dumps(data).encode()
        ciphertext = self.aead.encrypt(nonce, plaintext, None)
        # Result: Nonce (12) + Ciphertext + Tag (16)
        return nonce + ciphertext

    def decrypt_data(self, encrypted_blob: bytes) -> Dict:
        """Decrypt AES-256-GCM blob back to JSON."""
        nonce = encrypted_blob[:12]
        ciphertext = encrypted_blob[12:]
        plaintext = self.aead.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())

    def blind_filename(self, original_name: str) -> str:
        """Hash a filename to blind it from the Pod provider."""
        # Using HMAC ensures that even if two users have the same filename, 
        # their blinded names are different (since their keys are different)
        h = hmac.new(self.filename_key, original_name.encode(), hashlib.sha256)
        return h.hexdigest()

    def secure_save(self, base_path: str, filename: str, data: Dict):
        """Encrypt and save a blinded file to the local vault (which syncs to Pod)."""
        blinded_name = self.blind_filename(filename)
        target_path = os.path.join(base_path, blinded_name)
        
        # Save mapping for recovery/debugging (This mapping should ideally also be encrypted or kept local only)
        # For Phase 2, we store it in a local manifest
        encrypted_blob = self.encrypt_data(data)
        
        with open(target_path, "wb") as f:
            f.write(encrypted_blob)
            
        # Update manifest (local only)
        self._update_manifest(base_path, filename, blinded_name)

    def secure_load(self, base_path: str, filename: str) -> Optional[Dict]:
        """Load and decrypt a blinded file."""
        blinded_name = self.blind_filename(filename)
        target_path = os.path.join(base_path, blinded_name)
        
        if not os.path.exists(target_path):
            return None
            
        with open(target_path, "rb") as f:
            encrypted_blob = f.read()
            
        return self.decrypt_data(encrypted_blob)

    def _update_manifest(self, base_path: str, original: str, blinded: str):
        """Update a local, unencrypted manifest for development visibility."""
        manifest_path = os.path.join(base_path, "vault_manifest.json")
        manifest = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
            except:
                pass
        
        manifest[original] = blinded
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)
