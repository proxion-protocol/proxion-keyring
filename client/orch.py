import time
import requests
import json
from typing import List, Dict, Tuple
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

class Orchestrator:
    """Handles the connection lifecycle: Ticket Redemption -> RS Bootstrap."""
    
    def __init__(self, cp_url: str, rs_url: str):
        self.cp_url = cp_url.rstrip("/")
        self.rs_url = rs_url.rstrip("/")
        
    def redeem_ticket(self, 
                      ticket_id: str, 
                      identity_key: ed25519.Ed25519PrivateKey, 
                      webid: str, 
                      policies: List[Dict] = None,
                      aud: str = "wg0") -> Tuple[str, Dict]:
        """
        Redeem a ticket at the Control Plane.
        Returns: (token_id, receipt_payload)
        """
        # 1. Derive Pubkey Hex
        pub_bytes = identity_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        rp_pubkey = pub_bytes.hex()
        
        # 2. Prepare PoP
        nonce = str(time.time_ns())
        ts = int(time.time())
        holder_fingerprint = f"proxion-keyring-cli-{rp_pubkey[:8]}"
        
        # PoP Format: ticket_id|aud|nonce|ts
        msg = f"{ticket_id}|{aud}|{nonce}|{ts}".encode()
        signature = identity_key.sign(msg).hex()
        
        # 3. Request
        payload = {
            "ticket_id": ticket_id,
            "rp_pubkey": rp_pubkey,
            "aud": aud,
            "holder_key_fingerprint": holder_fingerprint,
            "pop_signature": signature,
            "nonce": nonce,
            "timestamp": ts,
            "webid": webid,
            "policies": policies or []
        }
        
        try:
            resp = requests.post(f"{self.cp_url}/tickets/redeem", json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            # Handle token format variance (string ID or object)
            token = data.get("token")
            if not token:
                token_data = data.get("token_data", {})
                token = token_data.get("token_id")
            
            if not token:
                raise ValueError("No token returned in redemption response")
                
            return token, data.get("receipt", {})
            
        except requests.exceptions.RequestException as e:
            # Try to get error detail
            detail = ""
            if e.response is not None:
                detail = f": {e.response.text}"
            raise RuntimeError(f"Redemption failed{detail}") from e

    def bootstrap_tunnel(self, token: str, identity_key: ed25519.Ed25519PrivateKey) -> str:
        """
        Exchange a valid token for a WireGuard configuration from the Resource Server.
        Returns: WireGuard config file content (str)
        """
        # RS needs our pubkey to configure the peer
        pub_bytes = identity_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        rp_pubkey = pub_bytes.hex()
        
        payload = {
            "token": token,
            "pubkey": rp_pubkey
        }
        
        try:
            resp = requests.post(f"{self.rs_url}/bootstrap", json=payload)
            resp.raise_for_status()
            
            data = resp.json()
            template = data.get("wg_config_template")
            if not template:
                # Fallback or error?
                # If RS didn't return a template, maybe it returned raw config?
                # For now assume Protocol compliance.
                raise ValueError("Response missing 'wg_config_template'")
                
            # Inject Private Key
            # We already have identity_key.
            private_bytes = identity_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            )
            import base64
            # WireGuard uses base64 encoded keys
            priv_b64 = base64.b64encode(private_bytes).decode('utf-8')
            
            final_config = template.replace("{{CLIENT_PRIVATE_KEY}}", priv_b64)
            return final_config
            
        except (requests.exceptions.RequestException, ValueError) as e:
            detail = ""
            if hasattr(e, 'response') and e.response is not None:
                detail = f": {e.response.text}"
            raise RuntimeError(f"Bootstrap failed{detail}") from e
