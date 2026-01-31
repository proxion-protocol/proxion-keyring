import pytest
import time
import json
from datetime import datetime, timezone
from cp.pod import PodClient
from cp.policy import PolicyEngine
from cp.control_plane import ControlPlane, ReceiptPayload

def test_pod_client_lifecycle(monkeypatch):
    responses = []
    
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code
        def json(self): return self.json_data
        def raise_for_status(self): pass

    def mock_request(method, url, **kwargs):
        if method == "GET":
            return MockResponse({"@id": url}, 200)
        if method == "PUT":
            return MockResponse(None, 201)
        if method == "DELETE":
            return MockResponse(None, 204)
        return MockResponse(None, 405)

    monkeypatch.setattr("requests.get", lambda url, **k: mock_request("GET", url, **k))
    monkeypatch.setattr("requests.put", lambda url, **k: mock_request("PUT", url, **k))
    monkeypatch.setattr("requests.delete", lambda url, **k: mock_request("DELETE", url, **k))
    
    client = PodClient("https://pod.example")
    
    # Test GET
    assert client.get_resource("/data")["@id"] == "https://pod.example/data"
    
    # Test WRITE
    assert client.write_resource("/data", {"val": 1}, "token") is True
    
    # Test DELETE
    assert client.delete_resource("/data", "token") is True

def test_receipt_serialization():
    receipt = ReceiptPayload(
        receipt_id="id1",
        who_webid="https://webid",
        what=[{"action": "a", "resource": "r"}],
        issued_at=1738290000, # Fixed stamp
        expires_at=1738293600,
        token_id="tok1",
        path="/path"
    )
    
    js = receipt.to_jsonld()
    assert js["@type"] == "Receipt"
    # ISO 8601 check: 2026-01-31T02:20:00+00:00 (example)
    assert "T" in js["issued_at"]
    assert "Z" in js["issued_at"] or "+00:00" in js["issued_at"]

def test_policy_engine_edge_cases():
    engine = PolicyEngine()
    
    # 1. Wildcard resource
    policies = [{
        "applies_to": {"all_devices": True},
        "permits": [{"action": "bootstrap", "resource": "*"}]
    }]
    assert engine.evaluate(policies, "bootstrap", "anything", "dev").allowed is True
    
    # 2. Resource prefix matching (Exact prefixed match logic)
    policies = [{
        "applies_to": {"all_devices": True},
        "permits": [{"action": "bootstrap", "resource": "rs:wg0"}]
    }]
    # Match exact
    assert engine.evaluate(policies, "bootstrap", "rs:wg0", "dev").allowed is True
    # Match un-prefixed (PolicyEngine currently matches if patterns match rs:{aud})
    assert engine.evaluate(policies, "bootstrap", "wg0", "dev").allowed is True

    # 3. Empty list or invalid format
    assert engine.evaluate([], "bootstrap", "wg0", "dev").allowed is False
    assert engine.evaluate([{"invalid": "format"}], "bootstrap", "wg0", "dev").allowed is False

def test_cp_invalid_inputs(tmp_path):
    store_file = tmp_path / "err_tickets.json"
    cp = ControlPlane(b"key"*8, str(store_file))
    
    mint = cp.mint_pt()
    tid = mint["ticket_id"]
    
    # 1. Invalid signature (garbage hex)
    with pytest.raises(ValueError, match="Invalid PoP signature"):
        cp.redeem_pt(
            ticket_id=tid,
            rp_pubkey="00"*32,
            aud="wg0",
            holder_key_fingerprint="fp",
            pop_signature="garbage",
            nonce="n",
            timestamp=int(time.time()),
            webid="me"
        )
        
    # 2. Missing Ticket
    with pytest.raises(ValueError, match="Unknown or expired ticket"):
        cp.redeem_pt("missing", "00"*32, "wg0", "fp", "sig", "n", 0, "me")

def test_cp_expiration(tmp_path):
    store_file = tmp_path / "exp_tickets.json"
    cp = ControlPlane(b"key"*8, str(store_file))
    cp.ticket_ttl_seconds = 1 # short ttl
    
    mint = cp.mint_pt()
    tid = mint["ticket_id"]
    
    time.sleep(1.1)
    
    with pytest.raises(ValueError, match="Unknown or expired ticket"):
        cp.redeem_pt(tid, "00"*32, "wg0", "fp", "sig", "n", 0, "me")
