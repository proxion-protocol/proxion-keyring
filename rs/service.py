"""Resource server for secure-channel bootstrap (Phase 4).

Validates tokens, returns connection material. WireGuard mutation behind feature flag.
"""

from __future__ import annotations

import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from proxion_core import Decision, RequestContext, Token, validate_request


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "KleitikonConnectionMaterial",
            "dp": self.dp,
            "interface": self.interface,
            "client": {"address": self.client_address, "dns": self.client_dns},
            "server": {"endpoint": self.server_endpoint, "pubkey": self.server_pubkey},
            "allowed_ips": self.allowed_ips,
            "expires_at": self.expires_at,
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
        # Check for NO_MUTATION env var (default: disabled)
        self._mutation_enabled = os.getenv("KLEITIKON_WG_MUTATION", "false").lower() == "true"
        # Simulated address pool counter
        self._next_address = 2

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
    ) -> ConnectionMaterial:
        """Bootstrap a secure channel.

        Validates token, allocates client address, returns connection material.
        """
        decision = self.authorize(token, ctx, proof)
        if not decision.allowed:
            raise PermissionError(f"Authorization denied: {decision.reason}")

        # Allocate client address
        client_addr = f"10.0.0.{self._next_address}/32"
        self._next_address += 1

        return ConnectionMaterial(
            dp="wireguard",
            interface=self._wg.interface,
            client_address=client_addr,
            client_dns=self._wg.dns,
            server_endpoint=self._wg.endpoint,
            server_pubkey=self._wg.server_pubkey or secrets.token_hex(32),
            allowed_ips=[self._wg.address_pool],
            expires_at=int(time.time()) + 3600,
        )

    def wg_peer_add(self, pubkey: str, allowed_ips: list[str]) -> None:
        """Add a WireGuard peer.

        Only executes if KLEITIKON_WG_MUTATION=true.
        """
        if not self._mutation_enabled:
            raise RuntimeError("WireGuard mutation disabled (NO_MUTATION mode)")
        if not self._wg.enabled:
            raise RuntimeError("WireGuard not enabled")
        # TODO: wg set wg0 peer <pubkey> allowed-ips <ips>
        raise NotImplementedError("wg_peer_add not yet implemented")

    def wg_peer_remove(self, pubkey: str) -> None:
        """Remove a WireGuard peer.

        Only executes if KLEITIKON_WG_MUTATION=true.
        """
        if not self._mutation_enabled:
            raise RuntimeError("WireGuard mutation disabled (NO_MUTATION mode)")
        if not self._wg.enabled:
            raise RuntimeError("WireGuard not enabled")
        # TODO: wg set wg0 peer <pubkey> remove
        raise NotImplementedError("wg_peer_remove not yet implemented")
