import os
import json
import base64
from typing import Dict, Any, Union
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

class CryptoError(Exception):
    """Generic crypto failure."""
    pass

class Cipher:
    """Wrapper for ChaCha20Poly1305 authenticated encryption."""
    
    def __init__(self, key: Union[str, bytes]):
        if isinstance(key, str):
            # Expect hex string or raw bytes? 
            # Ideally 32-byte key.
            # If plain string (like env var), we might need to hash it or expect hex.
            # Let's verify length.
            try:
                self.key = bytes.fromhex(key)
            except ValueError:
                # Fallback: if not hex, maybe raw bytes in latin1?
                # Or just error out to stricter.
                raise ValueError("Key must be hex string")
        else:
            self.key = key
            
        if len(self.key) != 32:
            raise ValueError(f"Key must be 32 bytes (got {len(self.key)})")
            
        self.aead = ChaCha20Poly1305(self.key)

    def encrypt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypts a dictionary into an EncryptedResource envelope."""
        try:
            # Canonical JSON dump (sort keys) to ensure stability if needed, 
            # though for pure storage it usually doesn't matter.
            plaintext = json.dumps(data, sort_keys=True).encode("utf-8")
            
            nonce = os.urandom(12)
            ciphertext = self.aead.encrypt(nonce, plaintext, None)
            
            return {
                "@context": "https://proxion.protocol/ontology/v1#",
                "@type": "EncryptedResource",
                "nonce": base64.b64encode(nonce).decode("utf-8"),
                "ciphertext": base64.b64encode(ciphertext).decode("utf-8"),
                "key_id": "v1" # Indicator for key rotation future-proofing
            }
        except Exception as e:
            raise CryptoError(f"Encryption failed: {e}") from e

    def decrypt(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypts an EncryptedResource envelope."""
        try:
            # Validate envelope
            if envelope.get("@type") != "EncryptedResource":
                # Maybe it's not encrypted?
                # Caller should decide policy. For now we strictly expect Envelope if called.
                raise CryptoError("Not an EncryptedResource")
                
            nonce_b64 = envelope.get("nonce")
            ciphertext_b64 = envelope.get("ciphertext")
            
            if not nonce_b64 or not ciphertext_b64:
                raise CryptoError("Missing nonce or ciphertext")
                
            nonce = base64.b64decode(nonce_b64)
            ciphertext = base64.b64decode(ciphertext_b64)
            
            plaintext = self.aead.decrypt(nonce, ciphertext, None)
            return json.loads(plaintext.decode("utf-8"))
            
        except Exception as e:
            raise CryptoError(f"Decryption failed: {e}") from e
