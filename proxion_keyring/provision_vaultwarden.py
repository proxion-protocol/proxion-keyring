
import os
import sys
import secrets
from proxion_keyring.identity import load_or_create_identity_key, derive_app_password

def provision_vaultwarden():
    # 1. Load Master Identity
    key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "identity_private.pem"))
    master_key = load_or_create_identity_key(key_path)
    
    # 2. Derive deterministic admin token (for /admin panel)
    admin_token = derive_app_password(master_key, "vaultwarden_admin")
    
    # 3. Derive deterministic master password for the user 'admin'
    master_password = derive_app_password(master_key, "vaultwarden_master")
    
    # 4. Path to .env or docker-compose override
    cli_dir = os.path.dirname(os.path.abspath(__file__))
    # Vaultwarden integration usually has a docker-compose.yml
    # We can inject environment variables via a .env file in its directory
    target_dir = os.path.abspath(os.path.join(cli_dir, "../../integrations/vaultwarden-integration"))
    env_file = os.path.join(target_dir, ".env")
    
    env_content = f"""
ADMIN_TOKEN={admin_token}
SIGNUPS_ALLOWED=true
ALLOW_HTTP_LOGIN=true
"""
    
    with open(env_file, "w") as f:
        f.write(env_content.strip())
        
    return {
        "admin_token": admin_token,
        "master_password": master_password
    }

if __name__ == "__main__":
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    res = provision_vaultwarden()
    print(f"Vaultwarden Provisioned.")
    print(f"Admin Token: {res['admin_token']}")
    print(f"Master Pass: {res['master_password']}")
