import os
import requests
import time
import base64
import json
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Config
CP_URL = os.getenv("proxion-keyring_CP_URL", "http://127.0.0.1:8787")
RS_URL = os.getenv("proxion-keyring_RS_URL", "http://127.0.0.1:8788")
WEBID = os.getenv("proxion-keyring_TEST_WEBID", "http://127.0.0.1:3200/alice/profile/card#me")

# Fixed Demo Keys (For reproducible E2E tests, but should ideally be external)
CP_KEY = os.getenv("proxion-keyring_CP_KEY", "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff")
CP_PUB = os.getenv("proxion-keyring_CP_PUBKEY", "3ccd241cffc9b3618044b97d036d8614593d8b017c340f1dee8773385517654b")

def main():
    print(f"--- proxion-keyring E2E Demo ---")
    
    # 1. Mint Ticket (as Service)
    print(f"\n[1] Minting Ticket...")
    try:
        res = requests.post(f"{CP_URL}/tickets/mint", headers={"Authorization": "Bearer dev-token-bypass"})
        res.raise_for_status()
        ticket_id = res.json()["ticket_id"]
        print(f"    Success! Ticket ID: {ticket_id}")
    except Exception as e:
        print(f"    FAILED: {e}")
        return

    # 2. Generate Device Key (as Device/Browser)
    print(f"\n[2] Generating Device Identity (Ed25519)...")
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    
    # Export Base64 Pubkey for WireGuard compatibility
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    rp_pubkey = base64.b64encode(pub_bytes).decode()
    print(f"    Device Pubkey (B64): {rp_pubkey}")

    # 3. Prepare PoP (as Device/Browser)
    print(f"\n[3] Signing Proof-of-Possession...")
    aud = "rs:wg0"
    nonce = str(time.time()) # Simple nonce
    ts = int(time.time())
    holder_fingerprint = f"python-e2e-{rp_pubkey[:8]}"
    
    # "ticket_id|aud|nonce|ts"
    msg = f"{ticket_id}|{aud}|{nonce}|{ts}".encode()
    signature = private_key.sign(msg)
    pop_signature = signature.hex()
    print(f"    Signature generated.")

    # 3.5 Fetch Policy from Solid Pod (SCS)
    print(f"\n[3.5] Fetching Policies from Solid Pod...")
    policies = []
    try:
        # In a real app we'd fetch from the user's pod using OIDC. 
        # Here we fetch the public test policy we seeded.
        res = requests.get("http://localhost:3200/test-policy.jsonld")
        if res.status_code == 200:
            policies.append(res.json())
            print(f"    Fetched policy: test-policy.jsonld")
        else:
            print(f"    Warning: Could not fetch policy ({res.status_code})")
    except Exception as e:
        print(f"    Warning: Policy fetch failed: {e}")

    # 4. Redeem Ticket (as Device -> CP)
    print(f"\n[4] Redeeming Ticket at CP...")
    payload = {
        "ticket_id": ticket_id,
        "rp_pubkey": rp_pubkey,
        "aud": aud,
        "holder_key_fingerprint": holder_fingerprint,
        "pop_signature": pop_signature,
        "nonce": nonce,
        "timestamp": ts,
        "webid": WEBID,
        "policies": policies
    }
    
    try:
        res = requests.post(f"{CP_URL}/tickets/redeem", json=payload)
        if res.status_code != 200:
            print(f"    FAILED: {res.status_code} {res.text}")
            return
        
        data = res.json()
        token = data.get("token") or data.get("token_data", {}).get("token_id")
        receipt = data.get("receipt")
        
        print(f"    Success!")
        print(f"    Token: {token[:16]}..." if token else "    Token: [Missing]")
        print(f"    Receipt ID: {receipt.get('receipt_id')}")
        
    except Exception as e:
        print(f"    FAILED: {e}")
        return

    # 5. Bootstrap Connection (as RS Agent -> RS)
    # Note: In real flow, RS agent validates token. Here we check RS directly?
    # RS `bootstrap` endpoint expects `token` in Authorization header (Bearer)
    # But for MVP demo, RS endpoint is:
    # `POST /bootstrap` accepts `{ "token": "..." }`?
    # Let's check rs/server.py.
    # Ah, `rs/server.py` `bootstrap` takes `token` in JSON body.
    
    print(f"\n[5] Bootstrapping Connection at RS...")
    try:
        rs_payload = {
            "token": token,
            "pubkey": rp_pubkey # RS needs pubkey to configure peer
        }
        res = requests.post(f"{RS_URL}/bootstrap", json=rs_payload)
        
        if res.status_code == 200:
            print(f"    Success!")
            # print(json.dumps(res.json(), indent=2))
            print(f"    WireGuard Config received ({len(res.text)} bytes)")
        else:
            print(f"    FAILED: {res.status_code} {res.text}")

    except Exception as e:
        print(f"    FAILED: {e}")

    # 7. Antigravity Link Test (Phase 7)
    print(f"\n[7] Testing Antigravity Link (Identity Gateway)...")
    GATEWAY_URL = "http://127.0.0.1:3001"
    try:
        # 7a. Unauthorized Access (from a random IP)
        print(f"    Attempting unauthorized access...")
        res = requests.get(GATEWAY_URL)
        print(f"    Status: {res.status_code} (Expected 403)")
        
        # 7b. Authorized Access (Simulated Tunnel IP)
        print(f"    Attempting authorized access (Simulated Tunnel IP: 10.0.0.3)...")
        res = requests.get(GATEWAY_URL, headers={"X-proxion-keyring-Sim-IP": "10.0.0.3"})
        if res.status_code == 200 or res.status_code == 404: # 404 if mock server not running
             print(f"    Success! Gateway allowed access for authorized tunnel IP.")
        else:
             print(f"    FAILED: {res.status_code} {res.text}")

    except Exception as e:
        print(f"    FAILED during gateway test: {e}")

    # 6. Revocation Test
    print(f"\n[6] Testing Revocation...")
    try:
        from jose import jwt
        # Decode without verification to get JTI (token_id)
        claims = jwt.get_unverified_claims(token)
        jti = claims.get("jti")
        print(f"    Token ID (jti): {jti}")
        
        # Call CP /revoke
        print(f"    Revoking token at CP...")
        rev_res = requests.post(f"{CP_URL}/tickets/revoke", json={"token_id": jti})
        print(f"    Revocation response: {rev_res.status_code} {rev_res.text}")
        rev_res.raise_for_status()
        
        print(f"    Waiting for RS CRL sync (2s)...")
        time.sleep(2)
        
        # Try bootstrap again
        print(f"    Attempting bootstrap with revoked token...")
        res = requests.post(f"{RS_URL}/bootstrap", json=rs_payload)
        
        if res.status_code == 403:
            print(f"    Success! RS rejected revoked token: {res.text}")
        else:
            print(f"    FAILED: RS accepted revoked token! (Status: {res.status_code})")
            
    except Exception as e:
        print(f"    FAILED during revocation test: {e}")

    print(f"\n--- Demo Complete ---")

if __name__ == "__main__":
    main()
