
import pytest
from unittest.mock import MagicMock, patch
import os
import sys

# Ensure import paths works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rs.server import app, SERIALIZER, SIGNING_KEY
from proxion_core import Token

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

from datetime import datetime, timedelta, timezone

def test_bootstrap_revocation(client):
    # 1. Create a valid token string
    # We use the real serializer and key from the app import
    token = Token(
        token_id="revoked-token-123",
        permissions=[],
        exp=datetime.now(timezone.utc) + timedelta(hours=1),
        aud="rs:wg0",
        caveats=[],
        holder_key_fingerprint="fp1",
    )
    # Patch expiration to be ignored or valid logic inside serializer?
    # Serializer sign creates standard JWT.
    
    # We need a valid JWT 
    # Let's import issue_token/mint_ticket to be proper? 
    # Or just use serializer directly.
    jwt_str = SERIALIZER.sign(token, SIGNING_KEY)

    # 2. Mock requests.get to return this token in CRL
    with patch("requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "revoked_tokens": ["revoked-token-123", "other-token"]
        }
        
        # 3. Request bootstrap
        # Force sync by mocking time or attribute?
        # The logic: if time.time() - last_sync > 30.
        # last_sync is 0 initially.
        
        res = client.post("/bootstrap", json={
            "token": jwt_str,
            "pubkey": "client-pubkey"
        })
        
        assert res.status_code == 403
        assert "Token Revoked" in res.json["error"]
        
        # Verify CRL was fetched
        mock_get.assert_called_with(os.getenv("proxion-keyring_CP_URL", "http://localhost:8787") + "/crl", timeout=2)

def test_bootstrap_valid_not_revoked(client):
    token = Token(
        token_id="valid-token-456",
        permissions=[("bootstrap", "rs:wg0")],
        exp=datetime.now(timezone.utc) + timedelta(hours=1),
        aud="rs:wg0",
        caveats=[],
        holder_key_fingerprint="fp1",
    )
    jwt_str = SERIALIZER.sign(token, SIGNING_KEY)

    # Mock RS service to succeed
    with patch("rs.server.rs.bootstrap_channel") as mock_bt:
        mock_bt.return_value.to_dict.return_value = {"success": True}
        
        with patch("requests.get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "revoked_tokens": ["revoked-token-123"]
            }
            
            res = client.post("/bootstrap", json={
                "token": jwt_str,
                "pubkey": "client-pubkey"
            })
            
            assert res.status_code == 200
            assert res.json["success"] is True

