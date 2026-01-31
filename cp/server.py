"""Kleitikon Control Plane Server (Flask).

Exposes real HTTP endpoints for ticket minting and redemption.
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dataclasses import asdict
from datetime import datetime, timezone

from .control_plane import ControlPlane

app = Flask(__name__)
# Allow CORS from localhost:3000 (app) and localhost:5173 (vite dev)
CORS(app, resources={r"/*": {
    "origins": ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    "allow_headers": ["Authorization", "Content-Type", "DPoP"]
}})

# Initialize Control Plane with Ed25519 signing key
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

cp_key_hex = os.getenv("KLEITIKON_CP_KEY")
if cp_key_hex:
    try:
        SIGNING_KEY = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(cp_key_hex))
    except Exception as e:
        print(f"ERROR: Failed to load KLEITIKON_CP_KEY: {e}")
        SIGNING_KEY = ed25519.Ed25519PrivateKey.generate()
else:
    # Use a fixed key for demo consistency if possible, or generate
    # For this demo, we'll generate and print for the RS to pick up if manually run.
    # But for E2E, we'll probably want a way to share it.
    SIGNING_KEY = ed25519.Ed25519PrivateKey.generate()

CP_PUBKEY_HEX = SIGNING_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
).hex()
print(f"--- CP STARTING ---")
print(f"KLEITIKON_CP_PUBKEY={CP_PUBKEY_HEX}")

cp = ControlPlane(signing_key=SIGNING_KEY, ticket_store_path="tickets_v2.json")

import requests
import proxion_core
from jose import jwt, jwk

def verify_solid_token(token):
    """Verify a Solid OIDC token and return the WebID.
    
    Note: For production, this should also verify DPoP proofs if using Access Tokens.
    For this spec-comportment demo, we verify the JWT signature against the issuer's JWKS.
    """
    if os.getenv("KLEITIKON_DEV_MODE") == "1" and token == "dev-token-bypass":
        print("WARN: Using Dev Mode Auth Bypass")
        return "https://localhost:3200/test-user/profile/card#me"

    try:
        # 1. Unverified header to get kid and issuer
        header = jwt.get_unverified_header(token)
        payload = jwt.get_unverified_claims(token)
        issuer = payload.get("iss")
        
        if not issuer:
            raise ValueError("Missing issuer in token")

        # 2. Fetch OIDC Config
        oidc_provider_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
        config = requests.get(oidc_provider_url).json()
        jwks_uri = config.get("jwks_uri")
        
        # 3. Fetch JWKS
        jwks = requests.get(jwks_uri).json()
        
        # 4. Verify JWT
        # NOTE: In production, you would verify 'aud' (client_id). 
        # For this demo, we allow any audience but ensure the signature is valid from the issuer.
        decoded = jwt.decode(
            token, 
            jwks, 
            algorithms=["RS256", "ES256"], 
            options={"verify_aud": False}
        )
        
        # 5. Extract WebID
        # Solid OIDC puts WebID in 'sub' or 'webid' claim
        webid = decoded.get("webid") or decoded.get("sub")
        return webid
    except Exception as e:
        print(f"Token verification failed: {e}")
        return None

@app.route("/tickets/revoke", methods=["POST"])
def revoke():
    """Revoke a token."""
    try:
        data = request.json
        token_id = data.get("token_id")
        if not token_id:
            return jsonify({"error": "Missing token_id"}), 400
        
        import sys
        sys.stderr.write(f"CP: Revoking token {token_id}\n")
        sys.stderr.flush()
        
        cp.revoke_token(token_id)
        return jsonify({"status": "revoked", "token_id": token_id}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/crl", methods=["GET"])
def get_crl():
    """Serve the Certificate Revocation List."""
    try:
        crl = cp.get_crl()
        import sys
        sys.stderr.write(f"CP: Serving CRL with {len(crl)} entries\n")
        sys.stderr.flush()
        return jsonify({"revoked_tokens": crl}), 200
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/tickets/mint", methods=["POST"])
def mint_ticket():
    """Mint a permission ticket (for RO)."""
    try:
        print(f"MINT REQUEST HEADERS: {request.headers}")
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Missing Authorization header"}), 401
        
        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0] not in ["Bearer", "DPoP"]:
            return jsonify({"error": "Invalid Authorization header format"}), 401
        
        token = parts[1]
        webid = verify_solid_token(token)
        
        if not webid:
            return jsonify({"error": "Invalid Solid OIDC token"}), 403
            
        print(f"Authenticated WebID for minting: {webid}")
        result = cp.mint_pt()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/tickets/redeem", methods=["POST"])
def redeem_ticket():
    """Redeem a permission ticket (for RP)."""
    try:
        data = request.json
        required = ["ticket_id", "rp_pubkey", "aud", "holder_key_fingerprint", "pop_signature", "nonce", "timestamp", "webid"]
        if not all(k in data for k in required):
            return jsonify({"error": "Missing required fields"}), 400

        # Now cp.redeem_pt returns (jwt_str, receipt_payload)
        jwt_token, receipt = cp.redeem_pt(
            ticket_id=data["ticket_id"],
            rp_pubkey=data["rp_pubkey"],
            aud=data["aud"],
            holder_key_fingerprint=data["holder_key_fingerprint"],
            pop_signature=data["pop_signature"],
            nonce=data["nonce"],
            timestamp=data["timestamp"],
            webid=data["webid"],
            policies=data.get("policies", [])
        )

        return jsonify({
            "token": jwt_token, 
            "receipt": receipt.to_jsonld(),
            "rs_hint": f"http://localhost:8788" # Demo hint
        }), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 403
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8787))
    app.run(host="127.0.0.1", port=port, debug=False)
