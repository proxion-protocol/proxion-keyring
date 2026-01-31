import subprocess
import shutil
from .base import WireGuardBackend, PeerConfig, validate_interface, validate_pubkey

class LinuxBackend(WireGuardBackend):
    """Linux WireGuard backend using wg command."""
    
    def __init__(self, use_sudo: bool = True):
        self._sudo = ["sudo"] if use_sudo else []
    
    def _run(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run command. Never uses shell=True."""
        return subprocess.run(
            self._sudo + cmd,
            capture_output=True,
            text=True,
            check=check,
        )
    
    def check_available(self) -> tuple[bool, str]:
        if not shutil.which("wg"):
            return False, "wg not found. Install: apt install wireguard-tools"
        
        # Verify wg is accessible (may fail without sudo)
        result = self._run(["wg", "--version"], check=False)
        if result.returncode != 0:
            return False, f"wg not accessible: {result.stderr}"
            
        return True, "WireGuard available"
    
    def add_peer(self, interface: str, peer: PeerConfig) -> None:
        interface = validate_interface(interface)
        
        # Note: persistent-keepalive is applied regardless of PSK
        self._run([
            "wg", "set", interface,
            "peer", peer.public_key,
            "allowed-ips", ",".join(peer.allowed_ips),
            "persistent-keepalive", str(peer.persistent_keepalive),
        ])
    
    def remove_peer(self, interface: str, public_key: str) -> None:
        interface = validate_interface(interface)
        public_key = validate_pubkey(public_key)
        self._run(["wg", "set", interface, "peer", public_key, "remove"])
    
    def list_peers(self, interface: str) -> list[str]:
        interface = validate_interface(interface)
        result = self._run(["wg", "show", interface, "peers"])
        
        # Split by newline and filter empty strings
        return [p for p in result.stdout.strip().split("\n") if p]
