"""Tests for WireGuard backend implementations."""
import pytest
import base64
from rs.backends.factory import create_backend, MockBackend
from rs.backends.base import PeerConfig
from rs.backends.linux import LinuxBackend

class TestValidation:
    """Tests for input validation."""
    
    def test_valid_pubkey(self):
        # 32 bytes valid base64
        valid_key = base64.b64encode(b"a" * 32).decode()
        config = PeerConfig(public_key=valid_key, allowed_ips=["10.0.0.1/32"])
        assert config.public_key == valid_key

    def test_invalid_pubkey_length(self):
        # 31 bytes
        invalid_key = base64.b64encode(b"a" * 31).decode()
        with pytest.raises(ValueError, match="Key must be 32 bytes"):
            PeerConfig(public_key=invalid_key, allowed_ips=["10.0.0.1/32"])

    def test_invalid_pubkey_base64(self):
        # Not base64
        with pytest.raises(ValueError, match="Invalid WireGuard public key"):
            PeerConfig(public_key="!@#$%", allowed_ips=["10.0.0.1/32"])

    def test_invalid_cidr(self):
        key = base64.b64encode(b"a" * 32).decode()
        with pytest.raises(ValueError, match="Invalid CIDR"):
            PeerConfig(public_key=key, allowed_ips=["999.999.999.999"])

class TestMockBackend:
    """Tests for mock backend logic."""
    
    def test_mock_backend_available(self):
        backend = MockBackend()
        available, msg = backend.check_available()
        assert available
        assert "Mock" in msg
    
    def test_mock_add_remove_peer(self):
        backend = MockBackend()
        key = base64.b64encode(b"B" * 32).decode()
        peer = PeerConfig(public_key=key, allowed_ips=["10.0.0.2/32"])
        
        backend.add_peer("wg-mock", peer)
        peers = backend.list_peers("wg-mock")
        assert key in peers
        
        backend.remove_peer("wg-mock", key)
        peers = backend.list_peers("wg-mock")
        assert key not in peers

class TestWindowsBackend:
    """Tests for Windows backend (only runs on Windows)."""
    
    def test_instantiation(self):
        import platform
        if platform.system().lower() != "windows":
            pytest.skip("Not running on Windows")
            
        from rs.backends.windows import WindowsBackend
        backend = WindowsBackend()
        # Should not raise exception
        assert backend is not None
        
        # avail check might fail if wg not installed, but method should run
        available, msg = backend.check_available()
        assert isinstance(available, bool)
        assert isinstance(msg, str)
