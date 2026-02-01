"""Control plane for proxion-keyring (Phase 3).

Protocol-only: no Solid auth server-side. Browser writes receipts to Pod.
"""

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from .store import FileStore
from .policy import PolicyEngine
from .pod import PodClient
from proxion_core import (
    Caveat,
    Token,
    issue_token,
    mint_ticket,
    redeem_ticket,
    RevocationList
)
from proxion_core.serialization import TokenSerializer


@dataclass(frozen=True)
class ReceiptPayload:
    """Receipt payload for browser to write to Pod."""
    receipt_id: str
    who_webid: str
    what: list[dict[str, str]]
    issued_at: int
    expires_at: int
    token_id: str
    path: str

    def to_jsonld(self, context_url: str = "https://proxion.protocol/ontology/v1#") -> dict[str, Any]:
        return {
            "@context": context_url,
            "@type": "Receipt",
            "receipt_id": self.receipt_id,
            "who": {"@type": "Person", "webid": self.who_webid},
            "what": self.what,
            "issued_at": datetime.fromtimestamp(self.issued_at, tz=timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(self.expires_at, tz=timezone.utc).isoformat(),
            "token_id": self.token_id,
        }


class ControlPlane:
    """proxion-keyring control plane service."""

    def __init__(self, signing_key: bytes, ticket_store_path: str = "tickets.json"):
        self.signing_key = signing_key
        self.ticket_ttl_seconds = 120
        self.token_ttl_seconds = 3600
        self._store = FileStore(ticket_store_path)
        self._policy_engine = PolicyEngine()
        self._revocation_list = RevocationList()
        self.serializer = TokenSerializer(issuer="https://proxion-keyring.example/cp")

    def mint_pt(self) -> dict[str, str]:
        """Mint a permission ticket."""
        ticket = mint_ticket(self.ticket_ttl_seconds)
        now = datetime.now(timezone.utc)
        self._store.set(ticket.ticket_id, {
            "created_at_ts": now.timestamp(),
            "redeemed": False,
        })
        return {
            "ticket_id": ticket.ticket_id,
            "as_uri": "https://proxion-keyring.example/cp", # TODO: dynamic
        }

    def redeem_pt(
        self,
        ticket_id: str,
        rp_pubkey: str,
        aud: str,
        holder_key_fingerprint: str,
        pop_signature: str,
        nonce: str,
        timestamp: int,
        webid: str,
        policies: list[dict] | None = None,
        now: datetime | None = None,
    ) -> tuple[Token, ReceiptPayload]:
        """Redeem a permission ticket with Solid policy evaluation."""
        if now is None:
            now = datetime.now(timezone.utc)

        # 1. Verify ticket existence and state
        self._store.purge_expired(self.ticket_ttl_seconds)
        ticket_info = self._store.get(ticket_id)
        if not ticket_info:
            raise ValueError("Unknown or expired ticket")
        if ticket_info["redeemed"]:
            raise ValueError("Ticket already redeemed")

        # 2. Verify PoP freshness
        req_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if abs((now - req_time).total_seconds()) > 60:
            raise ValueError("PoP timestamp out of bounds")

        # 3. Verify PoP signature (Ed25519)
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            import base64
            
            # Robustly decode public key (Hex or B64)
            pub_bytes = None
            if len(rp_pubkey) == 64: # Likely Hex
                 try:
                     pub_bytes = bytes.fromhex(rp_pubkey)
                 except: pass
            
            if pub_bytes is None: # Try B64
                 try:
                     pub_bytes = base64.b64decode(rp_pubkey)
                 except: pass
            
            if pub_bytes is None:
                 raise ValueError("Could not decode public key (must be 64-char hex or 44-char base64)")

            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            message = f"{ticket_id}|{aud}|{nonce}|{timestamp}".encode("utf-8")
            public_key.verify(bytes.fromhex(pop_signature), message)
        except Exception as e:
            raise ValueError(f"Invalid PoP signature: {e}")

        # 4. Policy Evaluation (Solid-First)
        # We assume policies are already fetched from the Pod (or passed by client)
        # The PolicyEngine handles the JSON-LD structure.
        result = self._policy_engine.evaluate(
            policies=policies or [],
            ctx_action="channel.bootstrap", # Normalized for this demo
            aud=aud,
            rp_pubkey=rp_pubkey
        )

        if not result.allowed:
            raise ValueError(result.reason or "Policy evaluation failed")

        # 5. Mark Redeemed
        ticket_info["redeemed"] = True
        self._store.set(ticket_id, ticket_info)

        # 6. Issue Token
        exp = now + timedelta(seconds=self.token_ttl_seconds)
        token = issue_token(
            permissions=result.permissions,
            exp=exp,
            aud=aud,
            caveats=[],
            holder_key_fingerprint=holder_key_fingerprint,
            signing_key=self.signing_key,
            now=now,
        )

        # 7. Serialize to JWT
        jwt_str = self.serializer.sign(token, self.signing_key)

        # 8. Build Receipt
        receipt_id = f"rcpt-{secrets.token_urlsafe(8)}"
        token_id_hash = hashlib.sha256(token.token_id.encode()).hexdigest()[:16]
        receipt = ReceiptPayload(
            receipt_id=receipt_id,
            who_webid=webid,
            what=[{"action": a, "resource": r} for a, r in sorted(result.permissions)],
            issued_at=int(now.timestamp()),
            expires_at=int(exp.timestamp()),
            token_id=f"sha256:{token_id_hash}",
            path=f"/proxion-keyring/receipts/{receipt_id}.jsonld",
        )

        return jwt_str, receipt

    def revoke_token(self, token_id: str, ttl_seconds: int = 3600):
        """Revoke a token locally and sync to Solid would be next."""
        self._revocation_list.revoke(token_id, datetime.now(timezone.utc), ttl_seconds)

    def get_crl(self) -> list[str]:
        """Return list of revoked token IDs (simulated CRL)."""
        return self._revocation_list.get_crl()

