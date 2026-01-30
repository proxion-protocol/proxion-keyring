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

# Initialize Control Plane with a fixed key for demo purposes
# In production, load from secure storage
SIGNING_KEY = os.getenv("KLEITIKON_CP_KEY", "demo-signing-key-must-be-32-bytes!!").encode()
cp = ControlPlane(signing_key=SIGNING_KEY)

import requests
from jose import jwt, jwk

def verify_solid_token(token):
    """Verify a Solid OIDC token and return the WebID.
    
    Note: For production, this should also verify DPoP proofs if using Access Tokens.
    For this spec-comportment demo, we verify the JWT signature against the issuer's JWKS.
    """
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

        token, receipt = cp.redeem_pt(
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
            "token": token.token_id,  # sending full token object might be better if client needs it, but token_id is usually the handle
            # Actually, proxion-core Token object might not be directly serializable.
            # Let's send the serialized token if possible or just the ID if that's what we use.
            # For now, assuming token.token_id is the capability string/handle.
            # Re-reading proxion-core: issue_token returns a Token object.
            # We should probably return the full token structure if it's opaque, but here we just send what's needed.
            # Let's serialize the minimal needed parts.
            "token_data": {
               "token_id": token.token_id,
               "exp": int(token.exp.timestamp()),
               "permissions": list(token.permissions)
            },
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
    app.run(host="127.0.0.1", port=port, debug=True)
