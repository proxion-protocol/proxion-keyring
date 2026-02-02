import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

from proxion_keyring.manager import KeyringManager

def test_keygen():
    print("Initializing Manager (should generate Server Identity)...")
    mgr = KeyringManager()
    
    if mgr.wg_server_priv and mgr.wg_server_pub and mgr.wg_server_pub != "DEMO_SERVER_PUBKEY":
        print(f"✅ Real Server Key Generated: {mgr.wg_server_pub}")
    else:
        print(f"❌ Server Key Mocked/Failed: {mgr.wg_server_pub}")
        
    print("\nGenerating Client Config...")
    conf = mgr.generate_client_config()
    
    if conf["public_key"] != "ERROR" and len(conf["public_key"]) > 10:
        print(f"✅ Real Client Key Generated: {conf['public_key']}")
        print(f"   Private: {conf['private_key'][:5]}...")
    else:
        print(f"❌ Client Key Failed")

    print("\nJSON Output Payload:")
    import json
    payload = {
        "server_endpoint": "10.0.0.1:51820",
        "server_pubkey": mgr.wg_server_pub,
        "client_private_key": conf["private_key"],
        "client_address": "10.0.0.x",
        "client_dns": "1.1.1.1",
        "pod_url": mgr.get_pod_url(),
        "bootstrap_token": "pre-authorized"
    }
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    test_keygen()
