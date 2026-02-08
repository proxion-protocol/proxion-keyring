import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from proxion_core.tokens import Token
from proxion_core.validator import validate_request, Decision
from proxion_core.context import RequestContext, Caveat

class Identity:
    """Core cryptographic identity management for Proxion."""
    
    def __init__(self, private_key):
        self.private_key = private_key
        self.public_key = private_key.public_key()

    def get_signing_key(self) -> bytes:
        """Derive an HMAC signing key from the master identity key."""
        raw_bytes = self.private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"proxion:token:signing",
        )
        return hkdf.derive(raw_bytes)

    def get_public_key_hex(self) -> str:
        """Get the public key as a hex string."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

    def validate_token(self, token_data: str, ctx_data: dict, proof: dict) -> Decision:
        """Validate a Proxion capability token."""
        try:
            raw = json.loads(token_data)
            
            # Rehydrate Caveats
            caveats = []
            for cid in raw.get("caveats", []):
                if cid.startswith("path_prefix:"):
                    prefix = cid.split(":", 1)[1]
                    caveats.append(Caveat(cid, lambda ctx, p=prefix: ctx.resource.startswith(p)))
            
            token = Token(
                token_id=raw["token_id"],
                permissions=frozenset(tuple(p) for p in raw["permissions"]),
                exp=datetime.fromisoformat(raw["exp"]),
                aud=raw["aud"],
                caveats=tuple(caveats), 
                holder_key_fingerprint=raw["holder_key_fingerprint"],
                alg=raw.get("alg", "HMAC-SHA256"),
                signature=raw["signature"]
            )
            
            ctx = RequestContext(
                action=ctx_data["action"],
                resource=ctx_data["resource"],
                aud=self.get_public_key_hex(),
                now=datetime.now(timezone.utc)
            )
            
            return validate_request(
                token=token,
                ctx=ctx,
                proof=proof,
                signing_key=self.get_signing_key()
            )
        except Exception as e:
            logging.error(f"Identity Validation Traceback: {e}")
            return Decision(False, f"Validation Error: {str(e)}")

    def sign_challenge(self, challenge: bytes) -> bytes:
        """Sign a challenge for Proof-of-Possession (PoP)."""
        # Note: Implement specific PoP signing logic if different from standard signatures
        return self.private_key.sign(
            challenge,
            # Placeholder for appropriate padding/algorithm if needed
        )
