from .base import WireGuardBackend, PeerConfig

class MockBackend(WireGuardBackend):
    """Mock backend for NO_MUTATION mode."""
    
    def __init__(self):
        self._peers: dict[str, list[str]] = {}
    
    def check_available(self) -> tuple[bool, str]:
        return True, "Mock backend (NO_MUTATION)"
    
    def add_peer(self, interface: str, peer: PeerConfig) -> None:
        if interface not in self._peers:
            self._peers[interface] = []
        if peer.public_key not in self._peers[interface]:
            self._peers[interface].append(peer.public_key)
    
    def remove_peer(self, interface: str, public_key: str) -> None:
        if interface in self._peers:
            self._peers[interface] = [k for k in self._peers[interface] if k != public_key]
    
    def list_peers(self, interface: str) -> list[str]:
        return self._peers.get(interface, [])

    def generate_keypair(self) -> tuple[str, str]:
        """Generate dummy keys."""
        return "MOCK_PRIVATE_KEY", "MOCK_PUBLIC_KEY"

    def get_public_from_private(self, private_key: str) -> str:
        """Derive dummy public key."""
        return f"MOCK_PUB_FOR_{private_key[:5]}"
