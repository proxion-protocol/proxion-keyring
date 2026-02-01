import subprocess
import shutil
import os
from typing import Optional
from .base import WireGuardBackend, PeerConfig, validate_interface, validate_pubkey

class LinuxBackend(WireGuardBackend):
    """Linux WireGuard backend using wg and ip commands."""
    
    def __init__(self, use_sudo_if_needed: bool = True):
        # On Linux, only root can modify network interfaces.
        # Check root safe for Windows
        try:
             self._is_root = os.geteuid() == 0
        except AttributeError:
             self._is_root = False # Windows user is not "root" in unix sense
        
        self._sudo = ["sudo"] if (use_sudo_if_needed and not self._is_root) else []
    
    def _run(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run command with optional sudo."""
        full_cmd = self._sudo + cmd
        # print(f"DEBUG EXECUTING: {' '.join(full_cmd)}") 
        return subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            check=check,
        )

    def check_available(self) -> tuple[bool, str]:
        # Need 'wg' (wireguard-tools) and 'ip' (iproute2)
        if not shutil.which("wg"):
            return False, "wg command not found. Please install wireguard-tools."
        if not shutil.which("ip"):
            return False, "ip command not found. Please install iproute2."
        
        # Check permissions (try a harmless read command)
        try:
            self._run(["wg", "show"], check=True)
        except subprocess.CalledProcessError:
            if not self._sudo:
                return False, "Insufficient permissions to run 'wg'. Run as root or enable sudo."
            # If sudo failed, it might be password prompt or something
            return False, "Could not execute 'wg' even with sudo. Check sudoers."
            
        return True, "WireGuard available"
    
    # --- Peer Management (Base Protocol) ---

    def add_peer(self, interface: str, peer: PeerConfig) -> None:
        interface = validate_interface(interface)
        # wg set <interface> peer <key> allowed-ips <ips> persistent-keepalive <secs>
        cmd = [
            "wg", "set", interface,
            "peer", peer.public_key,
            "allowed-ips", ",".join(peer.allowed_ips),
            "persistent-keepalive", str(peer.persistent_keepalive),
        ]
        self._run(cmd)
    
    def remove_peer(self, interface: str, public_key: str) -> None:
        interface = validate_interface(interface)
        public_key = validate_pubkey(public_key)
        self._run(["wg", "set", interface, "peer", public_key, "remove"])
    
    def list_peers(self, interface: str) -> list[str]:
        # wg show <interface> peers
        # Returns list of public keys, one per line
        interface = validate_interface(interface)
        try:
            res = self._run(["wg", "show", interface, "peers"])
            return [line.strip() for line in res.stdout.splitlines() if line.strip()]
        except subprocess.CalledProcessError:
            # Interface might not exist
            return []

    # --- Lifecycle Management (Extended) ---

    def ensure_interface(self, interface: str, private_key: str, listen_port: int, address_cidr: str) -> None:
        """Idempotently create and configure the WireGuard interface."""
        interface = validate_interface(interface)
        
        # 1. Check if exists
        exists = False
        try:
           self._run(["ip", "link", "show", interface])
           exists = True
        except subprocess.CalledProcessError:
           exists = False
           
        if not exists:
            # ip link add dev <interface> type wireguard
            self._run(["ip", "link", "add", "dev", interface, "type", "wireguard"])
        
        # 2. Configure private key and port
        # We need to write privkey to a temp file for 'wg setconf' or pass via stdin?
        # 'wg set' can take privkey-file. 
        # Easier: echo "private-key" | wg set <interface> private-key /dev/stdin
        
        # Subprocess input method for private key to avoid disk leaks
        priv_cmd = ["wg", "set", interface, "private-key", "/dev/stdin", "listen-port", str(listen_port)]
        proc = subprocess.run(
            self._sudo + priv_cmd, 
            input=private_key, 
            text=True, 
            capture_output=True, 
            check=True
        )
        
        # 3. Set IP Address
        # ip address add <cidr> dev <interface>
        # Check if address already assigned?
        # Easier: ip address replace ...
        self._run(["ip", "address", "replace", address_cidr, "dev", interface])

        # 4. Bring Up
        self._run(["ip", "link", "set", "up", "dev", interface])

    def delete_interface(self, interface: str) -> None:
        interface = validate_interface(interface)
        # ip link delete dev <interface>
        try:
            self._run(["ip", "link", "delete", "dev", interface])
        except subprocess.CalledProcessError:
            pass # Idempotent, ignore if already gone
