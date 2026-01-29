"""Control plane stub for Kleitikon (Phase 2 starter)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, List, Protocol
import secrets

from proxion_core import Caveat, Token, issue_token, mint_ticket, redeem_ticket

from .pod_storage import PodClient, write_receipt


@dataclass(frozen=True)
class PolicyDecision:
    permissions: set[tuple[str, str]]
    ttl_seconds: int
    caveats: list[Caveat]


class PolicyProvider(Protocol):
    def decide(self, rp_pubkey: str) -> PolicyDecision:
        ...


class ControlPlane:
    def __init__(
        self,
        signing_key: bytes,
        policy_provider: PolicyProvider,
        pod_client: PodClient,
        pod_base_url: str,
    ) -> None:
        self._signing_key = signing_key
        self._policy_provider = policy_provider
        self._pod_client = pod_client
        self._pod_base_url = pod_base_url.rstrip("/") + "/"

    def mint_pt(self, ttl_seconds: int) -> str:
        ticket = mint_ticket(ttl_seconds)
        return ticket.ticket_id

    def redeem_pt(
        self,
        ticket_id: str,
        rp_pubkey: str,
        aud: str,
        holder_key_fingerprint: str,
        now: datetime,
    ) -> Token:
        redeem_ticket(ticket_id, rp_pubkey, now)
        decision = self._policy_provider.decide(rp_pubkey)
        exp = now + timedelta(seconds=decision.ttl_seconds)
        token = issue_token(
            permissions=decision.permissions,
            exp=exp,
            aud=aud,
            caveats=decision.caveats,
            holder_key_fingerprint=holder_key_fingerprint,
            signing_key=self._signing_key,
            now=now,
        )
        receipt = {
            "type": "KleitikonReceipt",
            "receipt_id": f"rcpt-{secrets.token_urlsafe(8)}",
            "who": {"rp_pubkey": rp_pubkey},
            "what": [
                {"action": a, "resource": r} for (a, r) in sorted(decision.permissions)
            ],
            "issued_at": int(now.replace(tzinfo=timezone.utc).timestamp()),
            "expires_at": int(exp.replace(tzinfo=timezone.utc).timestamp()),
            "token_id": token.token_id,
        }
        write_receipt(self._pod_client, self._pod_base_url, receipt)
        return token
