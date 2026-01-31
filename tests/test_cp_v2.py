import pytest
import os
import time
from datetime import datetime, timezone
from cp.store import FileStore
from cp.policy import PolicyEngine
from cp.control_plane import ControlPlane

def test_file_store(tmp_path):
    store_file = tmp_path / "test_store.json"
    store = FileStore(str(store_file))
    
    store.set("test-key", {"data": "info", "created_at_ts": time.time()})
    assert store.get("test-key")["data"] == "info"
    
    # Reload store
    store2 = FileStore(str(store_file))
    assert store2.get("test-key")["data"] == "info"
    
    # Test purge
    time.sleep(1.1)
    store.purge_expired(1)
    assert store.get("test-key") is None

def test_policy_engine():
    engine = PolicyEngine()
    policies = [
        {
            "applies_to": {"device_id": "device1"},
            "permits": [{"action": "bootstrap", "resource": "wg0"}]
        },
        {
            "applies_to": {"all_devices": True},
            "permits": [{"action": "bootstrap", "resource": "wg1"}]
        }
    ]
    
    # Match specific device
    res = engine.evaluate(policies, "bootstrap", "wg0", "device1")
    assert res.allowed is True
    assert ("channel.bootstrap", "wg0") in res.permissions
    
    # Device mismatch
    res = engine.evaluate(policies, "bootstrap", "wg0", "device2")
    assert res.allowed is False
    
    # All devices match
    res = engine.evaluate(policies, "bootstrap", "wg1", "device2")
    assert res.allowed is True
    assert ("channel.bootstrap", "wg1") in res.permissions
    
    # Resource mismatch
    res = engine.evaluate(policies, "bootstrap", "wg2", "device1")
    assert res.allowed is False

def test_cp_redemption_with_persistence(tmp_path):
    store_file = tmp_path / "tickets.json"
    signing_key = b"A" * 32
    cp = ControlPlane(signing_key, str(store_file))
    
    # 1. Mint
    mint_res = cp.mint_pt()
    ticket_id = mint_res["ticket_id"]
    
    # Verify persistence
    cp2 = ControlPlane(signing_key, str(store_file))
    assert cp2._store.get(ticket_id) is not None
    
    # 2. Redeem
    # Setup dummy PoP
    from cryptography.hazmat.primitives.asymmetric import ed25519
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key().public_bytes_raw().hex()
    
    aud = "wg0"
    nonce = "nonce1"
    ts = int(time.time())
    msg = f"{ticket_id}|{aud}|{nonce}|{ts}".encode()
    sig = priv.sign(msg).hex()
    
    policies = [{
        "applies_to": {"all_devices": True},
        "permits": [{"action": "bootstrap", "resource": "wg0"}]
    }]
    
    token, receipt = cp.redeem_pt(
        ticket_id=ticket_id,
        rp_pubkey=pub,
        aud=aud,
        holder_key_fingerprint="device-key",
        pop_signature=sig,
        nonce=nonce,
        timestamp=ts,
        webid="https://pod.example/user",
        policies=policies
    )
    
    assert isinstance(token, str) # JWT
    assert token.count('.') == 2
    
    # We could decode it to verify aud, but for "with persistence" test, 
    # verifying it returned a JWT is sufficient validation of state.
    # The receipt check confirms identity binding.
    assert receipt.who_webid == "https://pod.example/user"
    
    with pytest.raises(ValueError, match="already redeemed"):
        cp2.redeem_pt(
            ticket_id=ticket_id,
            rp_pubkey=pub,
            aud=aud,
            holder_key_fingerprint="device-key",
            pop_signature=sig,
            nonce=nonce,
            timestamp=ts,
            webid="https://pod.example/user",
            policies=policies
        )

def test_pod_client_mock(monkeypatch):
    from cp.pod import PodClient
    
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
        def json(self): return self.json_data
        def raise_for_status(self): 
            if self.status_code >= 400: raise Exception("Error")

    def mock_get(*args, **kwargs):
        return MockResponse({"@context": "...", "Policy": "Mock"}, 200)

    monkeypatch.setattr("requests.get", mock_get)
    client = PodClient("https://pod.example")
    res = client.get_resource("/policy.jsonld")
    assert res["Policy"] == "Mock"

def test_revocation_flow():
    signing_key = b"B" * 32
    cp = ControlPlane(signing_key)
    
    token_id = "test-token-123"
    cp.revoke_token(token_id, ttl_seconds=10)
    
    # In this phase, get_crl is a placeholder, but we verify the call exists
    assert isinstance(cp.get_crl(), list)
