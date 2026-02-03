import os
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from proxion_keyring.identity import derive_app_password

def test_deterministic_password_derivation():
    # Use a fixed seed for testing
    seed = b"test_seed_exactly_32_bytes_long_" # 32 bytes
    master_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    
    # Derive password for 'adguard'
    pw1 = derive_app_password(master_key, "adguard")
    pw2 = derive_app_password(master_key, "adguard")
    
    # Must be deterministic
    assert pw1 == pw2
    assert len(pw1) == 16
    
    # Must be different for different apps
    pw_diff = derive_app_password(master_key, "other_app")
    assert pw1 != pw_diff

def test_password_format():
    seed = os.urandom(32)
    master_key = ed25519.Ed25519PrivateKey.from_private_bytes(seed)
    pw = derive_app_password(master_key, "test")
    
    # Should be hex-safe
    import re
    assert re.match(r"^[0-9a-f]{16}$", pw)
