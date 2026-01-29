"""Resource server stub for secure-channel bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from proxion_core import Decision, RequestContext, Token, validate_request


@dataclass
class WireGuardConfig:
    enabled: bool = False


class ResourceServer:
    def __init__(self, signing_key: bytes, wg: Optional[WireGuardConfig] = None) -> None:
        self._signing_key = signing_key
        self._wg = wg or WireGuardConfig(enabled=False)

    def authorize(self, token: Token, ctx: RequestContext, proof: object) -> Decision:
        return validate_request(token, ctx, proof, self._signing_key)

    def wg_peer_add(self, config: dict) -> None:
        if not self._wg.enabled:
            raise RuntimeError("wireguard mutation disabled")
        # TODO: add WireGuard peer
        raise NotImplementedError

    def wg_peer_remove(self, peer_id: str) -> None:
        if not self._wg.enabled:
            raise RuntimeError("wireguard mutation disabled")
        # TODO: remove WireGuard peer
        raise NotImplementedError
