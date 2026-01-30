"""Unit tests for Kleitikon Control Plane."""

import pytest
from datetime import datetime, timezone

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cp.control_plane import ControlPlane, ReceiptPayload


class TestControlPlane:
    """Tests for ControlPlane."""

    @pytest.fixture
    def cp(self):
        """Create a ControlPlane instance."""
        signing_key = b"test-signing-key-32-bytes-long!!"
        return ControlPlane(signing_key=signing_key)

    def test_mint_pt_returns_ticket_id(self, cp):
        """mint_pt should return a dict with ticket_id and as_uri."""
        result = cp.mint_pt()
        assert "ticket_id" in result
        assert "as_uri" in result
        assert len(result["ticket_id"]) > 0

    def test_mint_pt_creates_unique_tickets(self, cp):
        """Each mint_pt call should create a unique ticket."""
        t1 = cp.mint_pt()
        t2 = cp.mint_pt()
        assert t1["ticket_id"] != t2["ticket_id"]

    def test_redeem_pt_returns_token_and_receipt(self, cp):
        """redeem_pt should return Token and ReceiptPayload."""
        ticket = cp.mint_pt()
        now = datetime.now(timezone.utc)

        # Generate real keys
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        
        priv = ed25519.Ed25519PrivateKey.generate()
        pub = priv.public_key()
        rp_pubkey = pub.public_bytes(
            encoding=serialization.Encoding.Raw, 
            format=serialization.PublicFormat.Raw
        ).hex()
        
        # Sign
        ts = int(now.timestamp())
        nonce = "test-nonce"
        aud = "wg0"
        ticket_id = ticket["ticket_id"]
        msg = f"{ticket_id}|{aud}|{nonce}|{ts}".encode("utf-8")
        sig = priv.sign(msg).hex()

        token, receipt = cp.redeem_pt(
            ticket_id=ticket_id,
            rp_pubkey=rp_pubkey,
            aud=aud,
            holder_key_fingerprint="fingerprint",
            pop_signature=sig,
            nonce=nonce,
            timestamp=ts,
            webid="https://example.com/user#me",
            now=now,
        )

        assert token is not None
        assert token.token_id is not None
        assert isinstance(receipt, ReceiptPayload)
        assert receipt.who_webid == "https://example.com/user#me"
        assert receipt.path.startswith("/kleitikon/receipts/")

    def test_redeem_pt_single_use(self, cp):
        """Ticket should only be redeemable once."""
        ticket = cp.mint_pt()
        now = datetime.now(timezone.utc)

        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        
        priv = ed25519.Ed25519PrivateKey.generate()
        rp_pubkey = priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, 
            format=serialization.PublicFormat.Raw
        ).hex()
        
        ts = int(now.timestamp())
        nonce = "test-nonce"
        aud = "wg0"
        msg = f"{ticket['ticket_id']}|{aud}|{nonce}|{ts}".encode("utf-8")
        sig = priv.sign(msg).hex()

        # First redemption succeeds
        cp.redeem_pt(
            ticket_id=ticket["ticket_id"],
            rp_pubkey=rp_pubkey,
            aud=aud,
            holder_key_fingerprint="fingerprint",
            pop_signature=sig,
            nonce=nonce,
            timestamp=ts,
            webid="https://example.com/user#me",
            now=now,
        )

        # Second redemption fails
        with pytest.raises(ValueError, match="already redeemed"):
            cp.redeem_pt(
                ticket_id=ticket["ticket_id"],
                rp_pubkey=rp_pubkey,
                aud=aud,
                holder_key_fingerprint="fingerprint",
                pop_signature=sig,
                nonce=nonce,
                timestamp=ts,
                webid="https://example.com/user#me",
                now=now,
            )

    def test_redeem_unknown_ticket_fails(self, cp):
        """Redeeming an unknown ticket should fail."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="Unknown ticket"):
            cp.redeem_pt(
                ticket_id="nonexistent-ticket",
                rp_pubkey="00" * 32, # dummy 32-byte key
                aud="wg0",
                holder_key_fingerprint="fingerprint",
                pop_signature="sig",
                nonce="test-nonce",
                timestamp=int(now.timestamp()),
                webid="https://example.com/user#me",
                now=now,
            )

    def test_receipt_contains_no_network_metadata(self, cp):
        """Receipt should not contain endpoints or IPs."""
        ticket = cp.mint_pt()
        now = datetime.now(timezone.utc)

        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        
        priv = ed25519.Ed25519PrivateKey.generate()
        rp_pubkey = priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, 
            format=serialization.PublicFormat.Raw
        ).hex()
        
        ts = int(now.timestamp())
        nonce = "test-nonce"
        aud = "wg0"
        msg = f"{ticket['ticket_id']}|{aud}|{nonce}|{ts}".encode("utf-8")
        sig = priv.sign(msg).hex()

        _, receipt = cp.redeem_pt(
            ticket_id=ticket["ticket_id"],
            rp_pubkey=rp_pubkey,
            aud=aud,
            holder_key_fingerprint="fingerprint",
            pop_signature=sig,
            nonce=nonce,
            timestamp=ts,
            webid="https://example.com/user#me",
            now=now,
        )

        jsonld = receipt.to_jsonld()
        # Should not contain endpoint, ip, address keys
        assert "endpoint" not in str(jsonld).lower()
        assert "ip_address" not in str(jsonld).lower()
