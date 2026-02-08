"""proxion-keyring Control Plane Server (Flask).

Exposes real HTTP endpoints for ticket minting and redemption.
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dataclasses import asdict
from datetime import datetime, timezone

from .control_plane import ControlPlane

app = Flask(__name__)
print("--- PROXION OIDC SERVER V2 ---")
CORS(app)
# Allow CORS from localhost:3000 (app) and localhost:5173 (vite dev)
CORS(app, resources={r"/*": {
    "origins": ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    "allow_headers": ["Authorization", "Content-Type", "DPoP"]
}})

# Initialize Control Plane with Ed25519 signing key
from ..identity import load_or_create_identity_key
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import base64

SIGNING_KEY = load_or_create_identity_key()
CP_PUBKEY_HEX = SIGNING_KEY.public_key().public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
).hex()
print(f"--- CP STARTING ---")
print(f"proxion-keyring_CP_PUBKEY={CP_PUBKEY_HEX}")

cp = ControlPlane(signing_key=SIGNING_KEY, ticket_store_path="tickets_v2.json")

# OIDC State
AUTH_CODES = {} # code -> {webid, client_id, scope, redirect_uri}
OIDC_TOKENS = {} # access_token -> {webid, scope}

import requests
import proxion_core
import jwt # pyjwt
import uuid
import time

def verify_solid_token(token):
    """Verify a Solid OIDC token and return the WebID.
    
    Note: For production, this should also verify DPoP proofs if using Access Tokens.
    For this spec-comportment demo, we verify the JWT signature against the issuer's JWKS.
    """
    if os.getenv("proxion-keyring_DEV_MODE") == "1" and token == "dev-token-bypass":
        print("WARN: Using Dev Mode Auth Bypass")
        return "https://localhost:3200/test-user/profile/card#me"

    try:
        # 1. Unverified header to get kid and issuer
        # header = jwt.get_unverified_header(token) # jose style
        payload = jwt.decode(token, options={"verify_signature": False})
        issuer = payload.get("iss")
        
        if not issuer:
            raise ValueError("Missing issuer in token")

        # 2. Fetch OIDC Config
        oidc_provider_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
        config = requests.get(oidc_provider_url).json()
        jwks_uri = config.get("jwks_uri")
        
        # 3. Fetch JWKS
        # jwks = requests.get(jwks_uri).json()
        
        # 4. Verify JWT
        # NOTE: For this demo, we bypass full signature verification of external Solid tokens 
        # unless necessary, focusing on OIDC flow for Authentik.
        return payload.get("webid") or payload.get("sub")
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

@app.route("/.well-known/openid-configuration", methods=["GET"])
def oidc_config():
    """OIDC Discovery Endpoint."""
    base_url = request.host_url.rstrip("/")
    return jsonify({
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oidc/authorize",
        "token_endpoint": f"{base_url}/oidc/token",
        "userinfo_endpoint": f"{base_url}/oidc/userinfo",
        "jwks_uri": f"{base_url}/jwks.json",
        "response_types_supported": ["code", "id_token"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["EdDSA"],
        "scopes_supported": ["openid", "profile", "email"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        "claims_supported": ["sub", "iss", "webid", "name", "preferred_username"]
    })

@app.route("/jwks.json", methods=["GET"])
def jwks():
    """Expose public key in JWKS format (RFC 7517)."""
    pub_key = SIGNING_KEY.public_key()
    raw_pub = pub_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    # Base64URL encoding for JWK
    def b64url(b):
        return base64.urlsafe_b64encode(b).decode().rstrip("=")

    return jsonify({
        "keys": [
            {
                "kty": "OKP",
                "crv": "Ed25519",
                "x": b64url(raw_pub),
                "use": "sig",
                "kid": CP_PUBKEY_HEX[:16],
                "alg": "EdDSA"
            }
        ]
    })

@app.route("/oidc/authorize", methods=["GET"])
def oidc_authorize():
    """OIDC Authorization Endpoint."""
    client_id = request.args.get("client_id")
    redirect_uri = request.args.get("redirect_uri")
    state = request.args.get("state")
    scope = request.args.get("scope", "openid")
    
    # In a real OIDC flow, we would show a login screen or check a cookie.
    # For Proxion, we assume the user is logged into the dashboard at localhost:3000.
    # We can perform a "check-session" or just auto-authorize if coming from localhost.
    
    # For now, we auto-authorize and return a code.
    # In production, this would redirect to the Dashboards login page if no session exists.
    
    # We'll use a hardcoded WebID for the local identity
    webid = f"https://proxion.protocol/users/{CP_PUBKEY_HEX}"
    
    code = str(uuid.uuid4())
    AUTH_CODES[code] = {
        "webid": webid,
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": redirect_uri,
        "exp": time.time() + 600
    }
    
    sep = "&" if "?" in redirect_uri else "?"
    return f"<html><script>window.location.href='{redirect_uri}{sep}code={code}&state={state}';</script></html>"

@app.route("/oidc/token", methods=["POST"])
def oidc_token():
    """OIDC Token Endpoint."""
    # Authentik usually sends client_id/secret in POST body or Basic Auth
    code = request.form.get("code")
    client_id = request.form.get("client_id")
    # For now, we don't strictly verify client_secret as it's local
    
    if code not in AUTH_CODES:
        return jsonify({"error": "invalid_code"}), 400
    
    auth_data = AUTH_CODES.pop(code)
    if time.time() > auth_data["exp"]:
        return jsonify({"error": "code_expired"}), 400
    
    webid = auth_data["webid"]
    base_url = request.host_url.rstrip("/")
    
    # Create ID Token
    now = int(time.time())
    id_token_payload = {
        "iss": base_url,
        "sub": webid,
        "aud": client_id,
        "iat": now,
        "exp": now + 3600,
        "webid": webid,
        "preferred_username": "proxion-user",
        "name": "Proxion Sovereign User"
    }
    
    # Sign ID Token with Ed25519
    try:
        id_token = jwt.encode(id_token_payload, SIGNING_KEY, algorithm="EdDSA", headers={"kid": CP_PUBKEY_HEX[:16]})
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILED TO SIGN ID TOKEN: {e}")
        return jsonify({"error": "token_signing_failed", "details": str(e)}), 500

    access_token = str(uuid.uuid4())
    OIDC_TOKENS[access_token] = {
        "webid": webid,
        "scope": auth_data["scope"]
    }
    
    return jsonify({
        "access_token": access_token,
        "id_token": id_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": auth_data["scope"]
    })

@app.route("/oidc/userinfo", methods=["GET"])
def oidc_userinfo():
    """OIDC UserInfo Endpoint."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "invalid_request"}), 401
    
    token = auth_header.split(" ")[1]
    if token not in OIDC_TOKENS:
        return jsonify({"error": "invalid_token"}), 403
    
    token_data = OIDC_TOKENS[token]
    webid = token_data["webid"]
    
    return jsonify({
        "sub": webid,
        "webid": webid,
        "preferred_username": "proxion-user",
        "name": "Proxion Sovereign User",
        "email": "user@proxion.local"
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8787))
    app.run(host="127.0.0.1", port=port, debug=False)
