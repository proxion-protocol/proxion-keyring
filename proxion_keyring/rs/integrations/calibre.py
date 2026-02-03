import os
import sqlite3
from werkzeug.security import generate_password_hash
from ...identity import load_or_create_identity_key, derive_app_password

def get_db_path():
    """
    Locate the Calibre-Web database relative to the proxion-keyring package.
    Expected: ../integrations/calibre-integration/config/app.db
    """
    # this file is in proxion_keyring/rs/integrations/calibre.py
    # we want to go up to Desktop/Proxion/integrations
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Up to proxion_keyring package root
    pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    # Up to Desktop/Proxion (parent of proxion-keyring repo if we successfully found repo root)
    # Wait, 'pkg_root' above might be wrong depending on where 'proxion_keyring' is.
    # Let's assume standard layout:
    # Desktop/Proxion/
    #   proxion-keyring/
    #     proxion_keyring/
    #       rs/
    #         integrations/
    #           calibre.py
    #   integrations/
    #     calibre-integration/
    
    # So from current_dir:
    # ../../../.. -> proxion-keyring repo root
    # ../../../../.. -> Proxion root?
    
    # current_dir = .../proxion_keyring/rs/integrations
    # .. = rs
    # ../.. = proxion_keyring (package)
    # ../../.. = proxion-keyring (repo)
    # ../../../.. = Proxion (parent)
    
    proxion_root = os.path.abspath(os.path.join(current_dir, "../../../.."))
    db_path = os.path.join(proxion_root, "integrations", "calibre-integration", "config", "app.db")
    return db_path

def sync_credentials():
    """
    Force-sync the Calibre-Web 'admin' password to match the Sovereign Identity.
    """
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return False, f"Database not found at {db_path}"
        
    try:
        # Locate Identity Key
        # We assume the key is in the package root (standard location)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        key_path = os.path.abspath(os.path.join(current_dir, "../../identity_private.pem"))
        
        if not os.path.exists(key_path):
            return False, f"Identity key not found at {key_path}"
            
        identity_key = load_or_create_identity_key(key_path)
        password = derive_app_password(identity_key, "calibre")
        hashed_pw = generate_password_hash(password)
        
        # Connect to DB
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        
        # Update admin user
        # Note: Calibre-Web uses 'name' for username (usually).
        cur.execute("UPDATE user SET password = ? WHERE name = 'admin'", (hashed_pw,))
        
        if cur.rowcount == 0:
            con.close()
            return False, "User 'admin' not found in database."
            
        con.commit()
        con.close()
        
        return True, f"Synced. Password is: {password}"
        
    except Exception as e:
        return False, f"Sync Error: {str(e)}"
