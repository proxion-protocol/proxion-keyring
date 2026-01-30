"""Control plane for Kleitikon (Phase 3).

Protocol-only: no Solid auth server-side. Browser writes receipts to Pod.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from proxion_core import (
    Caveat,
    Token,
    issue_token,
    mint_ticket,
    redeem_ticket,
)


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

    def to_jsonld(self) -> dict[str, Any]:
        return {
            "@context": ["https://www.w3.org/ns/solid/terms"],
            "type": "KleitikonReceipt",
            "receipt_id": self.receipt_id,
            "who": {"webid": self.who_webid},
            "what": self.what,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "token_id": self.token_id,
            # Note: no endpoints/IPs per privacy posture
        }


@dataclass
class ControlPlane:
    """Kleitikon control plane service."""

    signing_key: bytes
    ticket_ttl_seconds: int = 120
    token_ttl_seconds: int = 3600

    # In-memory ticket store (for demo; production would use persistent store)
    _tickets: dict[str, dict] = field(default_factory=dict)

    def mint_pt(self) -> dict[str, str]:
        """Mint a permission ticket.

        Returns:
            dict with 'ticket_id' and 'as_uri' for QR encoding.
        """
        ticket = mint_ticket(self.ticket_ttl_seconds)
        self._tickets[ticket.ticket_id] = {
            "created_at": datetime.now(timezone.utc),
            "redeemed": False,
        }
        return {
            "ticket_id": ticket.ticket_id,
            "as_uri": "https://kleitikon.example/cp",  # TODO: configurable
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
        """Redeem a permission ticket.

        Args:
            ticket_id: The ticket to redeem.
            rp_pubkey: RP's public key (for future PoP verification).
            aud: Audience (RS identifier).
            holder_key_fingerprint: Fingerprint of holder's key.
            pop_signature: Ed25519 signature over 'ticket_id || aud || nonce || ts'.
            nonce: Freshness nonce.
            timestamp: Request timestamp.
            webid: RO's WebID (for receipt).
            now: Current time (for testing).

        Returns:
            Tuple of (Token, ReceiptPayload).

        Raises:
            ValueError: If ticket is invalid, expired, or already redeemed.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Verify ticket exists and is not redeemed
        ticket_info = self._tickets.get(ticket_id)
        if not ticket_info:
            raise ValueError("Unknown ticket")
        if ticket_info["redeemed"]:
            raise ValueError("Ticket already redeemed")

        # Verify freshness (timestamp within 60 seconds)
        req_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        if abs((now - req_time).total_seconds()) > 60:
            raise ValueError("PoP timestamp out of bounds")

        # Verify PoP signature
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            
            pub_bytes = bytes.fromhex(rp_pubkey)
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            
            sig_bytes = bytes.fromhex(pop_signature)
            # Canonical message format match agent/cli.py
            message = f"{ticket_id}|{aud}|{nonce}|{timestamp}".encode("utf-8")
            
            public_key.verify(sig_bytes, message)
        except Exception as e:
            raise ValueError(f"Invalid PoP signature: {e}") from e

        # Mark ticket as redeemed
        redeem_ticket(ticket_id, rp_pubkey, now)
        ticket_info["redeemed"] = True

        # Policy Check (Phase 11 Production Spec)
        # We iterate through policies provided by the client (fetched from Pod)
        # and check if any allow this RP/aud combination.
        valid_policy = False
        allowed_actions = set()

        provided_policies = policies or []
        print(f"CP: Validating against {len(provided_policies)} policies")
        for p in provided_policies:
            print(f"Checking policy: {p}")
            try:
                # Check if policy applies to this device
                applies = False
                applies_to = p.get("applies_to", {})
                if applies_to.get("all_devices"):
                    applies = True
                elif applies_to.get("device_id") == rp_pubkey:
                    applies = True
                
                if not applies:
                    continue

                # Check if policy permits this action/resource
                for perm in p.get("permits", []):
                    action = perm.get("action")
                    resource = perm.get("resource")
                    
                    # Wildcard or exact match
                    if action == "channel.bootstrap" and (resource == "*" or resource == aud or resource == f"rs:{aud}"):
                        valid_policy = True
                        allowed_actions.add((action, f"rs:{aud}"))
            except Exception as e:
                print(f"Error parsing policy: {e}")

        if not valid_policy:
            raise ValueError("No matching policy found in Pod for this device/resource")

        # Issue token with permissions from policies
        exp = now + timedelta(seconds=self.token_ttl_seconds)
        caveats: list[Caveat] = [] 

        token = issue_token(
            permissions=allowed_actions,
            exp=exp,
            aud=aud,
            caveats=caveats,
            holder_key_fingerprint=holder_key_fingerprint,
            signing_key=self.signing_key,
            now=now,
        )

        # Build receipt payload (no network metadata)
        receipt_id = f"rcpt-{secrets.token_urlsafe(8)}"
        token_id_hash = hashlib.sha256(token.token_id.encode()).hexdigest()[:16]
        receipt = ReceiptPayload(
            receipt_id=receipt_id,
            who_webid=webid,
            what=[{"action": a, "resource": r} for a, r in sorted(allowed_actions)],
            issued_at=int(now.timestamp()),
            expires_at=int(exp.timestamp()),
            token_id=f"sha256:{token_id_hash}",
            path=f"/kleitikon/receipts/{receipt_id}.jsonld",
        )

        return token, receipt
