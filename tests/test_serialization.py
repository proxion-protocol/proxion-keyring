import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt
from proxion_core import Token, Caveat
from proxion_core.serialization import TokenSerializer

TEST_KEY = b"test-secret-key-must-be-32-bytes!!"
SERIALIZER = TokenSerializer(issuer="https://test.cp")

def test_sign_and_verify_success():
    now = datetime.now(timezone.utc)
    exp = now + timedelta(hours=1)
    
    token = Token(
        token_id="tok_123",
        aud="rs:wg0",
        exp=exp,
        permissions=[("connect", "wg0")],
        caveats=[],
        holder_key_fingerprint="fp:abc",
        alg="EdDSA", # Internal alg, overriden by JWT
        signature=""
    )
    
    jwt_str = SERIALIZER.sign(token, TEST_KEY)
    assert isinstance(jwt_str, str)
    assert jwt_str.count(".") == 2
    
    # Verify
    decoded = SERIALIZER.verify(jwt_str, TEST_KEY, audience="rs:wg0")
    
    assert decoded.token_id == "tok_123"
    assert decoded.holder_key_fingerprint == "fp:abc"
    assert decoded.aud == "rs:wg0"
    # assert decoded.permissions[0] == ("connect", "wg0") # Tuple vs List issue might occur
    assert list(decoded.permissions[0]) == ["connect", "wg0"]

def test_verify_expired_fails():
    now = datetime.now(timezone.utc)
    exp = now - timedelta(seconds=1) # Expired
    
    token = Token(
        token_id="tok_exp",
        aud="rs", 
        exp=exp,
        permissions=[],
        caveats=[],
        holder_key_fingerprint="fp"
    )
    
    jwt_str = SERIALIZER.sign(token, TEST_KEY)
    
    with pytest.raises(ValueError, match="Signature has expired"):
        SERIALIZER.verify(jwt_str, TEST_KEY)

def test_verify_tampered_fails():
    token = Token("tok", "aud", datetime.now(timezone.utc)+timedelta(1), [], [], "fp")
    jwt_str = SERIALIZER.sign(token, TEST_KEY)
    
    # Tamper payload
    parts = jwt_str.split(".")
    import base64
    import json
    # Just append garbage to signature
    tampered = parts[0] + "." + parts[1] + "." + parts[2] + "garbage"
    
    with pytest.raises(ValueError, match="Invalid Token"):
        SERIALIZER.verify(tampered, TEST_KEY)

def test_verify_wrong_audience_fails():
    token = Token("tok", "aud:A", datetime.now(timezone.utc)+timedelta(1), [], [], "fp")
    jwt_str = SERIALIZER.sign(token, TEST_KEY)
    
    with pytest.raises(ValueError, match="Invalid audience"):
        SERIALIZER.verify(jwt_str, TEST_KEY, audience="aud:B")
