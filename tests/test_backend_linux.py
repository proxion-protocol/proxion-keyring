
import pytest
from unittest.mock import MagicMock, patch
import subprocess
from rs.backends.linux import LinuxBackend
from rs.backends.base import PeerConfig

@pytest.fixture
def backend():
    # Use non-sudo for testing checks, or force sudo mocked
    return LinuxBackend(use_sudo_if_needed=True)

class TestLinuxBackend:
    
    @patch("subprocess.run")
    @patch("shutil.which")
    @patch("os.geteuid", return_value=1000, create=True) # Create if missing (Windows)
    def test_check_available_success(self, mock_geteuid, mock_which, mock_run, backend):
        mock_which.side_effect = lambda x: "/usr/bin/" + x
        mock_run.return_value.returncode = 0
        
        # Force backend to think it's not root for this test
        backend._is_root = False
        backend._sudo = ["sudo"]
        
        avail, msg = backend.check_available()
        assert avail is True
        assert "WireGuard available" in msg
        
        # Should verify 'wg show' was called
        # mock_run checking is complex because of 'sudo' prefix
        # We can just verify it didn't raise
        
    @patch("subprocess.run")
    @patch("os.geteuid", return_value=1000, create=True)
    def test_add_peer_command(self, mock_geteuid, mock_run, backend):
        mock_run.return_value.returncode = 0
        
        backend._is_root = False
        backend._sudo = ["sudo"]
        
        peer = PeerConfig(
            public_key="a" * 43 + "=", # Valid b64 length
            allowed_ips=["10.0.0.2/32"]
        )
        
        backend.add_peer("wg0", peer)
        
        # Verify args
        args, kwargs = mock_run.call_args
        cmd = args[0]
        assert "sudo" in cmd
        assert "wg" in cmd
        assert "set" in cmd
        assert "wg0" in cmd
        assert "peer" in cmd
        assert peer.public_key in cmd
        assert "10.0.0.2/32" in cmd

    @patch("subprocess.run")
    def test_remove_peer_command(self, mock_run, backend):
        mock_run.return_value.returncode = 0
        pub = "b" * 43 + "="
        backend.remove_peer("wg0", pub)
        
        args, kwargs = mock_run.call_args
        cmd = args[0]
        # sudo wg set wg0 peer <pub> remove
        assert "remove" in cmd
        assert pub in cmd

    @patch("subprocess.run")
    def test_ensure_interface_creation(self, mock_run, backend):
        # Sequence: 
        # 1. ip link show -> failure (not exists)
        # 2. ip link add -> success
        # 3. wg set private key -> success
        # 4. ip address replace -> success
        # 5. ip link set up -> success
        
        # Setup mock for sequence
        # We need check=True to raise execution
        
        # Simulating 'ip link show' fails (1st call)
        # Then others succeed.
        
        # This is hard to model with single mock_run side_effect if logical branching exists in code.
        # But we can verify "ip link add" is called.
        
        mock_run.side_effect = [
             subprocess.CalledProcessError(1, "ip link show"), # 1. Check exists (fails)
             MagicMock(returncode=0), # 2. Add
             MagicMock(returncode=0), # 3. Set Key
             MagicMock(returncode=0), # 4. Set IP
             MagicMock(returncode=0), # 5. Set Up
        ]
        
        backend.ensure_interface("wg0", "privkey", 51820, "10.0.0.1/24")
        
        # check calls
        # We assume specific order. We can check any_call for criticals.
        cal_strs = [str(call[0][0]) for call in mock_run.call_args_list]
        
        # Check creation
        assert any("ip', 'link', 'add', 'dev', 'wg0', 'type', 'wireguard'" in c for c in cal_strs)
        # Check IP
        assert any("ip', 'address', 'replace', '10.0.0.1/24', 'dev', 'wg0'" in c for c in cal_strs)
        # Check Up
        assert any("ip', 'link', 'set', 'up', 'dev', 'wg0'" in c for c in cal_strs)

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
