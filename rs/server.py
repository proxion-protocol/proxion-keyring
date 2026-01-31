"""Kleitikon Resource Server (Flask).

Exposes real HTTP endpoints for secure channel bootstrap.
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS

from .service import ResourceServer, WireGuardConfig
# Need to import Token/RequestContext/validate_request from core if we want to reconstruct objects
# But for MVP we might mock the token validation if we don't transfer the full token object securely.
# In a real setup, the token is passed.
from proxion_core import Token, RequestContext, Decision

app = Flask(__name__)
CORS(app)

# Initialize Resource Server with CP's Public Key for token verification
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

cp_pub_hex = os.getenv("KLEITIKON_CP_PUBKEY", "3ccd241cffc9b3618044b97d036d8614593d8b017c340f1dee8773385517654b")
try:
    CP_PUBLIC_KEY = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(cp_pub_hex))
except Exception as e:
    print(f"ERROR: Failed to load CP Public Key: {e}")
    # Fallback to demo default if error
    CP_PUBLIC_KEY = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex("3ccd241cffc9b3618044b97d036d8614593d8b017c340f1dee8773385517654b"))

# Shared secret for other purposes if any, but Token signing is now asymmetric.
# We'll use a dummy bytes for ResourceServer init if it still expects symmetric (for legacy purposes)
DUMMY_KEY = b"dummy-key-for-legacy-init"

# WireGuard config
MSG_ENDPOINT = os.getenv("KLEITIKON_WG_ENDPOINT", "127.0.0.1:51820")
PUBKEY = os.getenv("KLEITIKON_WG_PUBKEY", "demo-pubkey")

wg_config = WireGuardConfig(
    enabled=True,
    interface="wg0",
    endpoint=MSG_ENDPOINT,
    server_pubkey=PUBKEY
)
# Strict RS (Phase 5)
rs = ResourceServer(signing_key=DUMMY_KEY, wg_config=wg_config)

from proxion_core.serialization import TokenSerializer

# Initialize Serializer
SERIALIZER = TokenSerializer(issuer="https://kleitikon.example/cp")

@app.route("/sessions", methods=["GET"])
def get_sessions():
    """Expose active sessions for the Identity Gateway."""
    return jsonify(rs._active_sessions), 200

@app.route("/bootstrap", methods=["POST"])
def bootstrap():
    """Bootstrap secure channel using JWT."""
    try:
        data = request.json
        jwt_str = data.get("token") or data.get("token_id")
        
        if not jwt_str:
             return jsonify({"error": "Missing token"}), 401

        # Verify JWT using CP's Public Key
        try:
            token = SERIALIZER.verify(jwt_str, CP_PUBLIC_KEY, audience="rs:wg0")
        except Exception as e:
            return jsonify({"error": f"Invalid token: {e}"}), 403

        # --- Revocation Check ---
        # TODO: Move to a proper service class.
        import requests
        import time
        
        crl_cache = getattr(app, "crl_cache", set())
        last_sync = getattr(app, "crl_last_sync", 0)
        
        # Sync if older than 1s (Demo speedup)
        if time.time() - last_sync > 1:
            try:
                cp_url = os.getenv("KLEITIKON_CP_URL", "http://localhost:8787")
                resp = requests.get(f"{cp_url}/crl", timeout=2)
                if resp.status_code == 200:
                    crl_data = resp.json().get("revoked_tokens", [])
                    crl_cache = set(crl_data)
                    setattr(app, "crl_cache", crl_cache)
                    setattr(app, "crl_last_sync", time.time())
                    print(f"Synced CRL: {len(crl_cache)} entries")
            except Exception as e:
                print(f"CRL Sync failed: {e}")
        
        if token.token_id in crl_cache:
            return jsonify({"error": "Token Revoked"}), 403
        # ------------------------

        # Reconstruct Request Context
        from datetime import datetime, timezone
        ctx = RequestContext(
            action="channel.bootstrap",
            resource="rs:wg0",
            aud="rs:wg0", # Token audience must match
            now=datetime.now(timezone.utc)
        )
        
        # Call RS Logic (now strict enabled if we remove MockRS)
        # But we are still using 'rs' which is 'MockResourceServer' instance created above.
        # We should replace that instance too, but MockRS.authorize checks alg="mock". 
        # Our real token has alg="HS256". 
        # So MockRS.authorize will fall through to super().authorize if alg!="mock".
        # Let's verify super().authorize calls proxion_core.validate_request.
        
        material = rs.bootstrap_channel(
            token=token,
            ctx=ctx,
            proof=None, # PoP verification for Token usage not strictly enforced here yet in spec? 
                        # Spec SEC 3.3 says "Subject MUST sign a challenge to exercise the Capability".
                        # Orchestrator does PoP for ticket redemption.
                        # For Token usage (Bootstrap), we technically should do PoP too.
                        # But typically Access Token is Bearer or DPoP. 
                        # Proxion Token is Capability.
                        # MVP: Bearer usage of JWT for now.
            client_pubkey=data.get("pubkey", "")
        )
        
        return jsonify(material.to_dict()), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8788))
    app.run(host="127.0.0.1", port=port, debug=False)
