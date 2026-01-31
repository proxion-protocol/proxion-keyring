from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from proxion_core import Decision, RequestContext, Token, validate_request
from .backends.factory import create_backend
from .backends.base import PeerConfig
from .address_pool import AddressPool


@dataclass
class WireGuardConfig:
    """WireGuard RS configuration."""
    enabled: bool = False
    interface: str = "wg0"
    endpoint: str = "example.com:51820"
    server_pubkey: str = ""
    address_pool: str = "10.0.0.0/24"
    dns: list[str] = field(default_factory=lambda: ["10.0.0.1"])


@dataclass
class ConnectionMaterial:
    """KleitikonConnectionMaterial response."""
    dp: str
    interface: str
    client_address: str
    client_dns: list[str]
    server_endpoint: str
    server_pubkey: str
    allowed_ips: list[str]
    expires_at: int
    wg_config_template: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "KleitikonConnectionMaterial",
            "dp": self.dp,
            "interface": self.interface,
            "client": {"address": self.client_address, "dns": self.client_dns},
            "server": {"endpoint": self.server_endpoint, "pubkey": self.server_pubkey},
            "allowed_ips": self.allowed_ips,
            "expires_at": self.expires_at,
            "wg_config_template": self.wg_config_template,
        }


class ResourceServer:
    """Kleitikon Resource Server."""

    def __init__(
        self,
        signing_key: bytes,
        wg_config: WireGuardConfig | None = None,
    ) -> None:
        self._signing_key = signing_key
        self._wg = wg_config or WireGuardConfig()
        
        # Address Pool
        self._address_pool = AddressPool(
            network=self._wg.address_pool,
            # Reserve .0 (network) and .1 (gateway)
            reserved=2, 
        )
        
        # Mutation mode (fail-closed)
        self._mutation_enabled = os.getenv("KLEITIKON_WG_MUTATION", "false").lower() == "true"
        
        if self._mutation_enabled:
            # Phase 1A: Only Linux mutation supported
            self._backend = create_backend(use_mock=False)
            available, msg = self._backend.check_available()
            if not available:
                # Hard fail if mutation requested but unavailable
                raise RuntimeError(f"KLEITIKON_WG_MUTATION=true but WireGuard unusable: {msg}")
        else:
            # Phase 1B: Mock backend for config-generation only
            self._backend = create_backend(use_mock=True)

    def authorize(self, token: Token, ctx: RequestContext, proof: object) -> Decision:
        """Validate a token against a request context.

        RS must NOT log token contents or keys.
        """
        return validate_request(token, ctx, proof, self._signing_key)

    def bootstrap_channel(
        self,
        token: Token,
        ctx: RequestContext,
        proof: object,
        client_pubkey: str,
    ) -> ConnectionMaterial:
        """Bootstrap a secure channel.

        Validates token, allocates client address, returns connection material.
        """
        decision = self.authorize(token, ctx, proof)
        if not decision.allowed:
            raise PermissionError(f"Authorization denied: {decision.reason}")

        # Allocate client address (safe, thread-safe, reusing leases)
        client_addr = self._address_pool.allocate(token.holder_key_fingerprint)

        # Mutate backend if enabled
        if self._mutation_enabled:
            peer = PeerConfig(
                public_key=client_pubkey,
                allowed_ips=[client_addr],
                persistent_keepalive=25,
            )
            self._backend.add_peer(self._wg.interface, peer)

        # Generate config template for client
        wg_template = self._generate_config_template(client_addr)

        return ConnectionMaterial(
            dp="wireguard",
            interface=self._wg.interface,
            client_address=client_addr,
            client_dns=self._wg.dns,
            server_endpoint=self._wg.endpoint,
            server_pubkey=self._wg.server_pubkey or "SERVER_PUBKEY_PLACEHOLDER",
            allowed_ips=[self._wg.address_pool],
            expires_at=int(time.time()) + 3600,
            wg_config_template=wg_template,
        )

    def _generate_config_template(self, client_addr: str) -> str:
        """Generate WireGuard config template."""
        return f"""# ============================================================
# KLEITIKON CONFIG TEMPLATE
# INSERT YOUR PRIVATE KEY LOCALLY. DO NOT SEND TO SERVER.
# ============================================================

[Interface]
Address = {client_addr}
DNS = {', '.join(self._wg.dns)}
PrivateKey = {{{{CLIENT_PRIVATE_KEY}}}}

[Peer]
PublicKey = {self._wg.server_pubkey or 'SERVER_PUBKEY_PLACEHOLDER'}
Endpoint = {self._wg.endpoint}
AllowedIPs = {self._wg.address_pool}
PersistentKeepalive = 25
"""

    def wg_peer_add(self, pubkey: str, allowed_ips: list[str]) -> None:
        """Add a WireGuard peer (Direct)."""
        if not self._mutation_enabled:
            raise RuntimeError("WireGuard mutation disabled (NO_MUTATION mode)")
            
        peer = PeerConfig(
            public_key=pubkey, 
            allowed_ips=allowed_ips,
            persistent_keepalive=25
        )
        self._backend.add_peer(self._wg.interface, peer)

    def wg_peer_remove(self, pubkey: str) -> None:
        """Remove a WireGuard peer (Direct)."""
        if not self._mutation_enabled:
            raise RuntimeError("WireGuard mutation disabled (NO_MUTATION mode)")
            
        self._backend.remove_peer(self._wg.interface, pubkey)
