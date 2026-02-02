
import os
import sys
from passlib.hash import bcrypt
from proxion_keyring.identity import load_or_create_identity_key, derive_app_password

def provision_adguard():
    # 1. Load Master Identity
    # Note: We need the absolute path to ensure we load the same key as the server/cli
    key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "identity_private.pem"))
    master_key = load_or_create_identity_key(key_path)
    
    # 2. Derive deterministic password
    raw_password = derive_app_password(master_key, "adguard")
    hashed_password = bcrypt.hash(raw_password)
    
    # 3. Path to config on Drive P: (Direct local path preferred for reliability)
    cli_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.abspath(os.path.join(cli_dir, "../../proxion-core/storage/network/adguard/conf/AdGuardHome.yaml"))
    
    if not os.path.exists(config_file):
        print(f"Error: AdGuard config not found at {config_file}")
        return None

    with open(config_file, "r") as f:
        content = f.read()

    # Simple replace for users section if already provisioned with admin/admin
    import re
    new_user_block = f"users:\n  - name: admin\n    password: {hashed_password}"
    content = re.sub(r"users:.*?\n  - name: admin\n    password: .*?\n", new_user_block + "\n", content, flags=re.DOTALL)

    with open(config_file, "w") as f:
        f.write(content)
        
    return raw_password

if __name__ == "__main__":
    # Ensure we are in the keyring package context
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    pw = provision_adguard()
    if pw:
        print(f"SUCCESS: Identity password provisioned.")
        print(f"NEW PASSWORD: {pw}")
