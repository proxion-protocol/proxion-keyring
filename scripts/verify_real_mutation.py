import requests
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519
from proxion_core import Token, RequestContext
from proxion_core.serialization import TokenSerializer

# 1. Setup Keys (must match RS config or be signed strictly)
# In server.py: CP_PUBLIC_KEY defaults to '3ccd...'
# We need the corresponding private key to sign a valid token.
# Based on tests/test_client_identity.py or similar, let's try to reverse it or just use a new keypair 
# and tell the User to restart RS with a specific ENV VAR if this fails.
# BUT, the server has a hardcoded default public key.
# Let's see if we can generate the specific private key that matches `3ccd...`
# If not, we will generate a NEW keypair and print the public key, asking the user to 
# set proxion-keyring_CP_PUBKEY when running the server.

# Actually, let's try to grab a known key from tests if possible.
# `test_cp_v2.py` uses random keys.
# Let's check if the default key in server.py is "well known" in the repo.
# It seems arbitrary.

# Strategy: I will generate a NEW CP Keypair here.
# AND I will generate a valid Token signed by it.
# I will print the PUBLIC KEY and instruct the agent/user to ensure the server trusts it.
# OR, since I cannot restart the server easily (User verifies), I might rely on `proxion-keyring_CP_PUBKEY` 
# being set by the user if I asked them to.
# Wait, I didn't ask them to set CP_PUBKEY in the previous turn. I only asked for WG_MUTATION.
# So the server is running with the default key `3ccd...`.
# I cannot sign a token for that unless I have the private key.

# WARNING: If I cannot verify, I cannot proceed.
# Let's restart. I will provide a script that ACTS as the Control Plane AND the Client.
# It will print: "Please restart RS with $env:proxion-keyring_CP_PUBKEY='...'"
# This is annoying for the user.

# Alternative: Is `3ccd...` from a deterministic seed?
# `3ccd...` is 32 bytes hex.
# Let's look at `server.py` again.
# `bytes.fromhex("3ccd241cffc9b3618044b97d036d8614593d8b017c340f1dee8773385517654b")`

# Let's search for this string in the codebase to see where it comes from.
# If I can't find the private key, I'll have to ask the user to restart the server with a key I control.

def main():
    print("Using default CP Private Key for testing...")
    
    # Use the default key that matches the server's default public key
    # Key from e2e_demo.py
    cp_priv_hex = "00112233445566778899aabbccddeeff00112233445566778899aabbccddeeff"
    try:
        cp_priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(cp_priv_hex))
        cp_pub = cp_priv.public_key()
        cp_pub_hex = cp_pub.public_bytes_raw().hex()
        print(f"[*] CP Public Key: {cp_pub_hex}")
        # Verify it matches the known default
        expected = "3ccd241cffc9b3618044b97d036d8614593d8b017c340f1dee8773385517654b"
        if cp_pub_hex != expected:
            print(f"[WARNING] Key mismatch! Server might reject token.")
            print(f"Expected: {expected}")
            print(f"Got:      {cp_pub_hex}")
    except Exception as e:
        print(f"[ERROR] Failed to load key: {e}")
        return

    # 2. Generate Client Keypair (for WireGuard)
    client_priv = ed25519.Ed25519PrivateKey.generate() # This is EdDSA, WG needs Curve25519
    # For WireGuard keys, we usually generate them via `wg genkey`.
    # But for the purpose of the API, it just expects a base64 string.
    # We can perform a mock one or generate a real one if `wg` is installed.
    # Let's just use a placeholder base64 string if we don't have python-wireguard-tools
    # Actually, `nacl` or `cryptography` can do X25519.
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives import serialization
    import base64
    
    wg_priv = x25519.X25519PrivateKey.generate()
    wg_pub = wg_priv.public_key()
    wg_pub_b64 = base64.b64encode(wg_pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )).decode()
    
    print(f"[*] Client WG Pubkey: {wg_pub_b64}")

    # 3. Mint a Token (Capability)
    # Allows 'channel.bootstrap' on 'rs:wg0' for 'device-test'
    serializer = TokenSerializer(issuer="https://proxion-keyring.example/cp")
    
    # 3. Mint a Token (Capability)
    serializer = TokenSerializer(issuer="https://proxion-keyring.example/cp")
    
    # Token dataclass: token_id, aud, exp, permissions, caveats, holder_key_fingerprint
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    
    token = Token(
        token_id=f"test-tok-{int(time.time())}",
        aud="rs:wg0",
        exp=exp,
        permissions=[("channel.bootstrap", "rs:wg0")],
        caveats=[], # No caveats for test
        holder_key_fingerprint="device-safe-zone-1"
    )
    
    jwt_str = serializer.sign(token, cp_priv)
    print(f"[*] Generated Token: {jwt_str[:20]}...")

    # 4. Call Bootstrap
    url = "http://127.0.0.1:8788/bootstrap"
    payload = {
        "token": jwt_str,
        "pubkey": wg_pub_b64
    }
    
    print(f"[*] Post to {url}...")
    try:
        resp = requests.post(url, json=payload, timeout=5)
        print(f"[*] Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print("\n[SUCCESS] Connection Material Received:")
            print(f"  Interface: {data.get('interface')}")
            print(f"  Client IP: {data['client']['address']}")
            print(f"  Server Endpoint: {data['server']['endpoint']}")
            print(f"  Config Template len: {len(data.get('wg_config_template', ''))}")
            
            # Save config for the user to try manually if they want
            with open("test_client.conf", "w") as f:
                cfg = data.get('wg_config_template', '')
                # Fill in private key
                # Note: cryptography exports X25519 private bytes, we need to base64 it
                wg_priv_b64 = base64.b64encode(wg_priv.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption()
                )).decode()
                cfg = cfg.replace("{{CLIENT_PRIVATE_KEY}}", wg_priv_b64)
                f.write(cfg)
            print("\n[!] Wrote 'test_client.conf' if you want to verify connection locally.")
            
        else:
            print(f"[FAIL] {resp.text}")
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")
        print("Ensure server is running on port 8788.")

if __name__ == "__main__":
    main()
