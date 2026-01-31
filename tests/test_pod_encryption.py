import pytest
import json
from unittest.mock import MagicMock
from cp.pod import PodClient
from proxion_core.crypto import Cipher

TEST_KEY = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"

@pytest.fixture
def cipher():
    return Cipher(TEST_KEY)

@pytest.fixture
def pod_client(cipher):
    return PodClient("http://pod.test", cipher=cipher)

def test_write_encrypts_payload(pod_client, monkeypatch):
    mock_put = MagicMock()
    mock_put.return_value.status_code = 201
    monkeypatch.setattr("requests.put", mock_put)
    
    data = {"secret": "plans", "list": [1, 2]}
    pod_client.write_resource("test.jsonld", data, "token")
    
    # Check that called data is encrypted
    call_kwargs = mock_put.call_args[1]
    sent_json = json.loads(call_kwargs["data"])
    
    assert sent_json["@type"] == "EncryptedResource"
    assert "ciphertext" in sent_json
    assert sent_json["ciphertext"] != ""
    assert "secret" not in json.dumps(sent_json) # Plaintext should not be visible

def test_read_decrypts_payload(pod_client, cipher, monkeypatch):
    # 1. Create a real encrypted payload
    original = {"foo": "bar"}
    encrypted_payload = cipher.encrypt(original)
    
    mock_get = MagicMock()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = encrypted_payload
    monkeypatch.setattr("requests.get", mock_get)
    
    # 2. Fetch
    result = pod_client.get_resource("test.jsonld", "token")
    
    # 3. Verify
    assert result == original
    assert result["foo"] == "bar"

def test_read_plaintext_passes_through(pod_client, monkeypatch):
    # If the pod has unencrypted data (e.g. public profile), it should pass through?
    # Or should we enforce?
    # Current implementation passes through if NOT EncryptedResource type.
    
    mock_get = MagicMock()
    mock_get.return_value.status_code = 200
    mock_get.return_value.json.return_value = {"@type": "PublicData", "hello": "world"}
    monkeypatch.setattr("requests.get", mock_get)
    
    result = pod_client.get_resource("public.jsonld", "token")
    assert result["hello"] == "world"

def test_no_cipher_writes_plaintext(monkeypatch):
    client = PodClient("http://pod.test", cipher=None)
    mock_put = MagicMock()
    mock_put.return_value.status_code = 201
    monkeypatch.setattr("requests.put", mock_put)
    
    data = {"plain": "text"}
    client.write_resource("msg", data, "tok")
    
    call_kwargs = mock_put.call_args[1]
    sent_json = json.loads(call_kwargs["data"])
    assert sent_json == data
