import requests
import time
import base64
import json
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# Config
CP_URL = "http://localhost:8787"
RS_URL = "http://localhost:8788"
WEBID = "http://localhost:3200/hobo/profile/card#me" # Change if needed

def main():
    print(f"--- Kleitikon E2E Demo ---")
    
    # 1. Mint Ticket (as Service)
    print(f"\n[1] Minting Ticket...")
    try:
        res = requests.post(f"{CP_URL}/tickets/mint")
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
    
    # Export Hex Pubkey
    pub_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    rp_pubkey = pub_bytes.hex()
    print(f"    Device Pubkey: {rp_pubkey[:16]}...")

    # 3. Prepare PoP (as Device/Browser)
    print(f"\n[3] Signing Proof-of-Possession...")
    aud = "wg0"
    nonce = str(time.time()) # Simple nonce
    ts = int(time.time())
    holder_fingerprint = f"python-e2e-{rp_pubkey[:8]}"
    
    # "ticket_id|aud|nonce|ts"
    msg = f"{ticket_id}|{aud}|{nonce}|{ts}".encode()
    signature = private_key.sign(msg)
    pop_signature = signature.hex()
    print(f"    Signature generated.")

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
        "webid": WEBID
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

    print(f"\n--- Demo Complete ---")

if __name__ == "__main__":
    main()
