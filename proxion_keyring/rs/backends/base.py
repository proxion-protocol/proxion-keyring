from abc import ABC, abstractmethod
from dataclasses import dataclass
import base64
import re
import ipaddress

# Valid generic interface name pattern (alphanumeric, dash, underscore)
INTERFACE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,15}$")

def validate_pubkey(key: str) -> str:
    """Validate WireGuard public key (32 bytes, base64)."""
    try:
        decoded = base64.b64decode(key, validate=True)
        if len(decoded) != 32:
            raise ValueError("Key must be 32 bytes")
    except Exception as e:
        raise ValueError(f"Invalid WireGuard public key: {e}")
    return key

def validate_interface(name: str) -> str:
    if not INTERFACE_PATTERN.match(name):
        raise ValueError(f"Invalid interface name: {name}")
    return name

@dataclass
class PeerConfig:
    public_key: str
    allowed_ips: list[str]
    persistent_keepalive: int = 25
    
    def __post_init__(self):
        self.public_key = validate_pubkey(self.public_key)
        # Validate allowed_ips as CIDR
        for ip in self.allowed_ips:
            try:
                ipaddress.ip_network(ip, strict=False)
            except ValueError as e:
                raise ValueError(f"Invalid CIDR: {ip}") from e

class WireGuardBackend(ABC):
    @abstractmethod
    def check_available(self) -> tuple[bool, str]:
        """Check if WireGuard mutation is available."""
        pass
    
    @abstractmethod
    def add_peer(self, interface: str, peer: PeerConfig) -> None:
        """Add a peer to an existing interface."""
        pass
    
    @abstractmethod
    def remove_peer(self, interface: str, public_key: str) -> None:
        """Remove a peer from an interface."""
        pass
    
    @abstractmethod
    def list_peers(self, interface: str) -> list[str]:
        """List public keys of all peers on an interface."""
        pass

    @abstractmethod
    def generate_keypair(self) -> tuple[str, str]:
        """Generate a new (private_key, public_key) pair."""
        pass
    
    @abstractmethod
    def get_public_from_private(self, private_key: str) -> str:
        """Derive public key from private key."""
        pass
