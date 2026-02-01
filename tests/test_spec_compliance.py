
"""
Proxion Spec Compliance Tests (Normative Invariants)
Referencing PROXION_UI_SPEC.md Section 7.
"""
import pytest
import time
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cp.control_plane import ControlPlane
from proxion_core import validate_request, Token, RequestContext, Decision

@pytest.fixture
def cp():
    signing_key = ed25519.Ed25519PrivateKey.generate()
    return ControlPlane(signing_key=signing_key)

@pytest.fixture
def keys():
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, 
        format=serialization.PublicFormat.Raw
    ).hex()
    return priv, pub

class TestNormativeInvariants:
    
    def test_i2_single_use_tickets(self, cp, keys):
        """I2: A Permission Ticket MUST NOT be redeemable more than once."""
        priv, pub = keys
        
        # 1. Mint
        pt = cp.mint_pt()
        
        # 2. Redeem Once
        now = datetime.now(timezone.utc)
        ts = int(now.timestamp())
        msg = f"{pt['ticket_id']}|wg0|nonce|{ts}".encode()
        sig = priv.sign(msg).hex()
        
        PERMIT_ALL = [{"applies_to": {"all_devices": True}, "permits": [{"action": "bootstrap", "resource": "wg0"}]}]
        
        cp.redeem_pt(pt['ticket_id'], pub, "wg0", "print", sig, "nonce", ts, "webid", PERMIT_ALL, now)
        
        # 3. Redeem Again -> FAIL
        with pytest.raises(ValueError, match="already redeemed"):
            cp.redeem_pt(pt['ticket_id'], pub, "wg0", "print", sig, "nonce", ts, "webid", PERMIT_ALL, now)

    def test_i3_finite_authority(self, cp, keys):
        """I3: All tickets and capabilities MUST be time-bounded."""
        priv, pub = keys
        pt = cp.mint_pt()
        
        # Verify Ticket TTL (Mocking time passing)
        cp.ticket_ttl_seconds = 1
        time.sleep(1.1)
        
        now = datetime.now(timezone.utc)
        ts = int(now.timestamp())
        msg = f"{pt['ticket_id']}|wg0|nonce|{ts}".encode()
        sig = priv.sign(msg).hex()
        PERMIT_ALL = [{"applies_to": {"all_devices": True}, "permits": [{"action": "bootstrap", "resource": "wg0"}]}]

        with pytest.raises(ValueError, match="Unknown or expired ticket"):
             cp.redeem_pt(pt['ticket_id'], pub, "wg0", "print", sig, "nonce", ts, "webid", PERMIT_ALL, now)

    def test_i4_contextual_authorization(self, cp):
        """I4: Authorization decisions MUST depend on request context."""
        # Setup a token that allows "bootstrap" on "wg0"
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        token = Token(
            token_id="t1", aud="wg0", exp=exp, 
            permissions=[("bootstrap", "wg0")], 
            caveats=[], holder_key_fingerprint="f", alg="EdDSA"
        )
        
        signing_key = b"irrelevant_for_logic_check"
        
        # Case A: Correct Context
        ctx_ok = RequestContext(action="bootstrap", resource="wg0", aud="wg0", now=datetime.now(timezone.utc))
        decision = validate_request(token, ctx_ok, None, signing_key)
        assert decision.allowed
        
        # Case B: Wrong Action (e.g. "delete")
        ctx_bad_act = RequestContext(action="delete", resource="wg0", aud="wg0", now=datetime.now(timezone.utc))
        decision = validate_request(token, ctx_bad_act, None, signing_key)
        assert not decision.allowed
        
        # Case C: Wrong Resource (e.g. "wg1")
        ctx_bad_res = RequestContext(action="bootstrap", resource="wg1", aud="wg0", now=datetime.now(timezone.utc))
        decision = validate_request(token, ctx_bad_res, None, signing_key)
        assert not decision.allowed

    def test_i6_audience_binding(self):
        """I6: Authorization MUST bind tokens to an intended audience."""
        exp = datetime.now(timezone.utc) + timedelta(hours=1)
        token = Token(
            token_id="t1", aud="target-service", exp=exp, 
            permissions=[("bootstrap", "target-service")], 
            caveats=[], holder_key_fingerprint="f", alg="EdDSA"
        )
        
        # Request sent to WRONG audience
        ctx = RequestContext(action="bootstrap", resource="target-service", aud="evil-service", now=datetime.now(timezone.utc))
        
        decision = validate_request(token, ctx, None, b"")
        assert not decision.allowed
        assert "audience" in decision.reason.lower()

if __name__ == "__main__":
    sys.exit(pytest.main(["-v", __file__]))
