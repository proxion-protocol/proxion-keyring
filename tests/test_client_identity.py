import pytest
import os
import json
import stat
from client.identity import IdentityManager
from cryptography.hazmat.primitives.asymmetric import ed25519

def test_ensure_storage_creates_dir(tmp_path):
    storage = tmp_path / ".kleitikon"
    assert not storage.exists()
    
    IdentityManager(str(storage))
    assert storage.exists()
    assert storage.is_dir()

def test_generate_identity_creates_file(tmp_path):
    storage = tmp_path / "id_test"
    mgr = IdentityManager(str(storage))
    
    key = mgr.get_identity()
    assert isinstance(key, ed25519.Ed25519PrivateKey)
    assert (storage / "device.key").exists()
    
    # Verify file permissions (best effort check on non-Windows)
    if os.name == 'posix':
        mode = os.stat(storage / "device.key").st_mode
        assert mode & 0o777 == 0o600

def test_load_existing_identity(tmp_path):
    storage = tmp_path / "persist_test"
    mgr = IdentityManager(str(storage))
    
    key1 = mgr.get_identity()
    pub1 = mgr.get_public_key_hex(key1)
    
    # Reload
    mgr2 = IdentityManager(str(storage))
    key2 = mgr2.get_identity()
    pub2 = mgr2.get_public_key_hex(key2)
    
    assert pub1 == pub2

def test_corrupt_identity_handling(tmp_path):
    storage = tmp_path / "corrupt_test"
    mgr = IdentityManager(str(storage))
    
    # Create garbage file
    with open(storage / "device.key", "w") as f:
        f.write("{ invalid json")
        
    with pytest.raises(ValueError, match="Corrupt identity"):
        mgr.get_identity()
