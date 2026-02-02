from typing import Any, Dict
from datetime import datetime, timezone
import jwt
from . import Token, Caveat

class TokenSerializer:
    """Handles serialization of Tokens to/from JWT using PyJWT."""

    def __init__(self, issuer: str = "https://proxion.protocol"):
        self.issuer = issuer

    def sign(self, token: Token, private_key: Any) -> str:
        """Sign a Token object into a JWT string using EdDSA (PyJWT)."""
        payload = {
            "iss": self.issuer,
            "sub": token.holder_key_fingerprint,
            "aud": token.aud,
            "exp": int(token.exp.timestamp()), 
            "jti": token.token_id,
            "proxion:act": [list(p) for p in token.permissions],
            "proxion:cav": [vars(c) for c in token.caveats],
        }
        
        return jwt.encode(payload, private_key, algorithm="EdDSA")

    def verify(self, token_str: str, public_key: Any, audience: str = None) -> Token:
        """Verify a JWT string using EdDSA (PyJWT) and return a Token object."""
        try:
            payload = jwt.decode(
                token_str, 
                public_key, 
                algorithms=["EdDSA"],
                audience=audience
            )
            
            permissions = [tuple(p) for p in payload.get("proxion:act", [])]
            
            caveats_data = payload.get("proxion:cav", [])
            caveats = []
            for c_data in caveats_data:
                c_type = c_data.get("type", "unknown")
                c_params = c_data.get("parameters", {})
                caveats.append(Caveat(type=c_type, **c_params))

            return Token(
                token_id=payload["jti"],
                aud=payload.get("aud"),
                exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
                permissions=permissions,
                caveats=caveats,
                holder_key_fingerprint=payload["sub"],
                alg="EdDSA",
                signature="jwt-verified" 
            )
        except Exception as e:
            raise ValueError(f"Invalid Token: {e}") from e
