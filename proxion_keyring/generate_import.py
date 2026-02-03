
import json
import os
from proxion_keyring.identity import load_or_create_identity_key, derive_app_password

def generate_bw_import():
    # 1. Load Master Identity
    key_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "identity_private.pem"))
    master_key = load_or_create_identity_key(key_path)
    
    apps = [
        {"id": "adguard", "name": "AdGuard Home", "url": "http://localhost:3002"},
        {"id": "archivebox", "name": "ArchiveBox", "url": "http://localhost:8090"},
        {"id": "calibre", "name": "Calibre-Web", "url": "http://localhost:8083"},
        {"id": "vaultwarden_admin", "name": "Vaultwarden Admin Panel", "url": "https://localhost:8086/admin"},
        {"id": "vaultwarden_master", "name": "Vaultwarden Master Password", "url": "https://localhost:8086"}
    ]
    
    bw_items = []
    
    for app in apps:
        pw = derive_app_password(master_key, app["id"])
        item = {
            "type": 1, # Login
            "name": app["name"],
            "notes": f"Deterministically generated for Proxion Suite ({app['id']})",
            "login": {
                "username": "admin",
                "password": pw,
                "uris": [{"match": None, "uri": app["url"]}]
            }
        }
        bw_items.append(item)
        
    import_data = {
        "items": bw_items
    }
    
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "proxion_vault_import.json"))
    with open(output_path, "w") as f:
        json.dump(import_data, f, indent=4)
        
    return output_path

if __name__ == "__main__":
    path = generate_bw_import()
    print(f"IMPORT_FILE_CREATED: {path}")
