import pytest
from unittest.mock import MagicMock
from cryptography.hazmat.primitives.asymmetric import ed25519
from client.orch import Orchestrator

@pytest.fixture
def identity():
    return ed25519.Ed25519PrivateKey.generate()

@pytest.fixture
def orchestrator():
    return Orchestrator("http://cp", "http://rs")

def test_redeem_ticket_success(orchestrator, identity, monkeypatch):
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "token": "tok_123",
        "receipt": {"id": "rcpt_1"}
    }
    monkeypatch.setattr("requests.post", mock_post)
    
    token, receipt = orchestrator.redeem_ticket("tick_1", identity, "webid")
    
    assert token == "tok_123"
    assert receipt["id"] == "rcpt_1"
    
    # Verify strict PoP signature presence
    call_args = mock_post.call_args[1]["json"]
    assert "pop_signature" in call_args
    assert call_args["ticket_id"] == "tick_1"

def test_redeem_ticket_failure(orchestrator, identity, monkeypatch):
    import requests
    mock_post = MagicMock()
    mock_post.return_value.raise_for_status.side_effect = requests.exceptions.RequestException("403 Forbidden")
    mock_post.return_value.text = "Error"
    monkeypatch.setattr("requests.post", mock_post)
    
    with pytest.raises(RuntimeError, match="Redemption failed"):
        orchestrator.redeem_ticket("tick_1", identity, "webid")

def test_bootstrap_tunnel_success(orchestrator, identity, monkeypatch):
    mock_post = MagicMock()
    mock_post.return_value.status_code = 200
    # Return JSON with template
    mock_post.return_value.json.return_value = {
        "wg_config_template": "[Interface]\nPrivateKey={{CLIENT_PRIVATE_KEY}}\nAddress=10.0.0.2"
    }
    monkeypatch.setattr("requests.post", mock_post)
    
    config = orchestrator.bootstrap_tunnel("tok_123", identity)
    
    # Verify substitution
    assert "[Interface]" in config
    assert "PrivateKey=" in config
    assert "{{CLIENT_PRIVATE_KEY}}" not in config
    assert "Address=10.0.0.2" in config
    
    # Verify payload
    call_args = mock_post.call_args[1]["json"]
    assert call_args["token"] == "tok_123"
    assert "pubkey" in call_args
