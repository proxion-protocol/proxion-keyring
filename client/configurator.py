import abc
import sys
import platform
import subprocess
import tempfile
import stat
import os
from pathlib import Path

class Configurator(abc.ABC):
    """Abstract base class for applying WireGuard configurations."""

    @abc.abstractmethod
    def apply_config(self, interface_name: str, config_content: str) -> None:
        pass

    @abc.abstractmethod
    def remove_config(self, interface_name: str) -> None:
        pass

class WindowsConfigurator(Configurator):
    """Windows implementation using wg.exe."""

    def _get_wg_exe(self) -> str:
        # Check PATH first, then standard install location
        wg = "wg.exe"
        try:
            subprocess.run([wg, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return wg
        except FileNotFoundError:
            pass
            
        standard_path = r"C:\Program Files\WireGuard\wg.exe"
        if Path(standard_path).exists():
            return standard_path
            
        raise RuntimeError("WireGuard (wg.exe) not found. Please install WireGuard for Windows.")

    def apply_config(self, interface_name: str, config_content: str) -> None:
        wg_exe = self._get_wg_exe()
        
        # Write config to a temp file
        # Note: wg.exe on Windows requires the file to have .conf extension
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as tmp:
            tmp.write(config_content)
            tmp_path = tmp.name
        
        try:
            # Install tunnel service
            # Usage: wg.exe installtunnelservice [path/to/conf]
            cmd = [wg_exe, "installtunnelservice", tmp_path]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise RuntimeError(f"Failed to install tunnel: {result.stderr}")
                
        finally:
            # Cleanup temp file
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def remove_config(self, interface_name: str) -> None:
        wg_exe = self._get_wg_exe()
        
        # Uninstall tunnel service
        # Usage: wg.exe uninstalltunnelservice [interface_name]
        cmd = [wg_exe, "uninstalltunnelservice", interface_name]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            # Ignore error if service doesn't exist? 
            # wg.exe usually complains if service not found.
            # We raise so caller knows state is unclean.
            raise RuntimeError(f"Failed to uninstall tunnel: {result.stderr}")

class LinuxConfigurator(Configurator):
    """Linux implementation using wg-quick."""

    def apply_config(self, interface_name: str, config_content: str) -> None:
        # Write to /etc/wireguard/{interface_name}.conf
        # This typically requires sudo.
        # For CLI usage, we might write to /tmp and run `sudo wg-quick up /tmp/conf`?
        # Standard: /etc/wireguard/
        
        conf_path = Path(f"/etc/wireguard/{interface_name}.conf")
        
        # We can't easily write to /etc without sudo.
        # This Configurator assumes it has sufficient permissions OR we use a temp path.
        # wg-quick accepts a path.
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as tmp:
            tmp.write(config_content)
            tmp_path = tmp.name
            
        try:
            subprocess.run(["wg-quick", "up", tmp_path], check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"wg-quick up failed: {e}")
        finally:
            os.remove(tmp_path)

    def remove_config(self, interface_name: str) -> None:
        # To tear down, we ideally need the config file again if we used arbitrary path.
        # If we used interface name, wg-quick looks in /etc/wireguard.
        # If we used temp file, we can't easily tear down later unless we keep the file.
        
        # Better approach for Linux CLI:
        # 1. Check if we have sudo.
        # 2. Write to /etc/wireguard/wg0.conf
        # 3. wg-quick up wg0
        
        # For this PoC, we'll try `wg-quick down interface_name` assuming it was installed to /etc 
        # OR we admit limitation: removing arbitrary-path tunnels is hard without the file.
        # Let's assume standard system path management for Linux for now.
        
        subprocess.run(["wg-quick", "down", interface_name], check=True)

def get_configurator() -> Configurator:
    sys_plat = platform.system()
    if sys_plat == "Windows":
        return WindowsConfigurator()
    elif sys_plat == "Linux":
        return LinuxConfigurator()
    else:
        raise NotImplementedError(f"Unsupported platform: {sys_plat}")
