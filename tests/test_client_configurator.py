import pytest
from unittest.mock import MagicMock, patch
import platform
from client.configurator import get_configurator, WindowsConfigurator, LinuxConfigurator

def test_factory_returns_correct_class():
    plat = platform.system()
    configurator = get_configurator()
    
    if plat == "Windows":
        assert isinstance(configurator, WindowsConfigurator)
    elif plat == "Linux":
        assert isinstance(configurator, LinuxConfigurator)

@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_windows_apply_config(monkeypatch):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    monkeypatch.setattr("subprocess.run", mock_run)
    
    # Mock existence of wg.exe
    monkeypatch.setattr("pathlib.Path.exists", lambda x: True)
    
    conf = WindowsConfigurator()
    # We need to mock _get_wg_exe to avoid searching actual system
    conf._get_wg_exe = lambda: "c:\\fake\\wg.exe"
    
    conf.apply_config("wg0", "[Interface]\n...")
    
    assert mock_run.called
    args = mock_run.call_args[0][0]
    assert args[0] == "c:\\fake\\wg.exe"
    assert args[1] == "installtunnelservice"
    assert args[2].endswith(".conf")

@pytest.mark.skipif(platform.system() != "Windows", reason="Windows only")
def test_windows_remove_config(monkeypatch):
    mock_run = MagicMock()
    mock_run.return_value.returncode = 0
    monkeypatch.setattr("subprocess.run", mock_run)
    
    conf = WindowsConfigurator()
    conf._get_wg_exe = lambda: "wg.exe"
    
    conf.remove_config("wg0")
    
    args = mock_run.call_args[0][0]
    assert args[1] == "uninstalltunnelservice"
    assert args[2] == "wg0"
