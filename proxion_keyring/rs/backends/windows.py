import subprocess
import shutil
import os
from .base import WireGuardBackend, PeerConfig, validate_interface, validate_pubkey

class WindowsBackend(WireGuardBackend):
    """Windows WireGuard backend using wg command."""
    
    def __init__(self):
        # Locate wg.exe
        self._wg_exe = shutil.which("wg") or r"C:\Program Files\WireGuard\wg.exe"
        self._dry_run = os.getenv("proxion-keyring_WG_DRY_RUN", "false").lower() == "true"
        
    def _run(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run command or simulate if dry_run enabled."""
        import sys
        
        full_cmd_str = f'"{self._wg_exe}" ' + " ".join(cmd)
        if self._dry_run:
            sys.stderr.write(f"WG_DRY_RUN: {full_cmd_str}\n")
            sys.stderr.flush()
            # Return a mock completed process
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        full_cmd = [self._wg_exe] + cmd
        return subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            check=check,
        )
    
    def check_available(self) -> tuple[bool, str]:
        if not os.path.exists(self._wg_exe):
            return False, f"wg.exe not found at {self._wg_exe} or in PATH. Install WireGuard for Windows."
        
        # Verify execution
        try:
            result = self._run(["--version"], check=False)
            if result.returncode != 0:
                return False, f"wg execution failed: {result.stderr}"
        except OSError as e:
            return False, f"Failed to execute wg: {e}"
            
        return True, "WireGuard available"
    
    def add_peer(self, interface: str, peer: PeerConfig) -> None:
        interface = validate_interface(interface)
        
        # Note: persistent-keepalive is applied regardless of PSK
        self._run([
            "set", interface,
            "peer", peer.public_key,
            "allowed-ips", ",".join(peer.allowed_ips),
            "persistent-keepalive", str(peer.persistent_keepalive),
        ])
    
    def remove_peer(self, interface: str, public_key: str) -> None:
        interface = validate_interface(interface)
        public_key = validate_pubkey(public_key)
        self._run(["set", interface, "peer", public_key, "remove"])
    
    def list_peers(self, interface: str) -> list[str]:
        interface = validate_interface(interface)
        result = self._run(["show", interface, "peers"])
        
        # Split by newline and filter empty strings
        # Windows newlines might be \r\n, strip handles it
        return [p for p in result.stdout.strip().split("\n") if p]

    def generate_keypair(self) -> tuple[str, str]:
        """Generate a new private/public key pair using wg genkey | wg pubkey."""
        # We can't easily pipe in subprocess.run without shell=True which is risky.
        # Instead, run genkey, then run pubkey.
        
        # 1. Generate Private Key
        res_priv = self._run(["genkey"])
        if res_priv.returncode != 0:
            raise RuntimeError(f"Failed to generate private key: {res_priv.stderr}")
        private_key = res_priv.stdout.strip()
        
        # 2. Derive Public Key
        public_key = self.get_public_from_private(private_key)
        
        return private_key, public_key

    def get_public_from_private(self, private_key: str) -> str:
        """Derive public key from private key using wg pubkey."""
        # Pass private key via stdin
        full_cmd = [self._wg_exe, "pubkey"]
        
        import subprocess
        try:
            # We must use proper subprocess.run with input
            # If dry_run, return dummy
            if self._dry_run:
                print(f"WG_DRY_RUN: echo {private_key[:5]}... | wg pubkey")
                return "DUMMY_PUBKEY_FROM_" + private_key[:5]

            proc = subprocess.run(
                full_cmd,
                input=private_key,
                text=True,
                capture_output=True,
                check=True
            )
            return proc.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to derive public key: {e.stderr}")
