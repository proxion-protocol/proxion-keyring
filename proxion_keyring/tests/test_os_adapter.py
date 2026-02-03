import pytest
import unittest
from unittest.mock import MagicMock, patch, mock_open
from proxion_keyring.os_adapter import WindowsAdapter, LinuxAdapter, MacAdapter

def test_windows_adapter_dc_command():
    adapter = WindowsAdapter()
    app_path = "C:/fake/app"
    local_storage = "C:/fake/storage"
    
    # Mock os.path.exists and open to simulate compose files
    mock_content = "  app:\n    volumes:\n      - P:/data:/app/data\n"
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data=mock_content)), \
         patch("os.makedirs", MagicMock()):
        
        cmd = adapter.get_docker_compose_cmd(app_path, local_storage, ["up", "-d"])
        
        # Verify it includes the generated override
        assert "docker-compose.proxion-local.yml" in str(cmd)
        assert "-f" in cmd
        assert "up" in cmd

def test_linux_adapter_dc_command():
    adapter = LinuxAdapter()
    cmd = adapter.get_docker_compose_cmd("/fake/path", "/fake/storage")
    
    # Linux should just return standard command
    assert cmd == ["docker-compose", "up", "-d"]

def test_windows_dns_enable_logic():
    adapter = WindowsAdapter()
    # Mock elevation
    adapter._elevate_ps = MagicMock()
    
    adapter.set_dns(16, "127.0.0.1")
    
    # Verify the PS command string
    called_ps = adapter._elevate_ps.call_args[0][0]
    assert "Set-DnsClientServerAddress" in called_ps
    assert "-InterfaceIndex 16" in called_ps
    assert "-ServerAddresses 127.0.0.1" in called_ps

def test_mac_adapter_dns_logic():
    adapter = MacAdapter()
    with patch("subprocess.run") as mock_run:
        adapter.set_dns("Wi-Fi", "127.0.0.1")
        called_cmd = mock_run.call_args[0][0]
        assert "networksetup" in called_cmd
        assert "-setdnsservers" in called_cmd
        assert "Wi-Fi" in called_cmd
        assert "127.0.0.1" in called_cmd

def test_mac_adapter_reset_dns_logic():
    adapter = MacAdapter()
    with patch("subprocess.run") as mock_run:
        adapter.reset_dns("Ethernet")
        called_cmd = mock_run.call_args[0][0]
        assert "-setdnsservers" in called_cmd
        assert "Ethernet" in called_cmd
        assert "Empty" in called_cmd
