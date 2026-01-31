import pytest
import os
import json
from proxion_core.crypto import Cipher, CryptoError

# A valid 32-byte hex key
TEST_KEY_HEX = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f"

def test_cipher_init_validates_key():
    # Valid
    Cipher(TEST_KEY_HEX)
    Cipher(bytes.fromhex(TEST_KEY_HEX))
    
    # Invalid length
    with pytest.raises(ValueError, match="32 bytes"):
        Cipher("0001") # Too short
        
    # Invalid hex
    with pytest.raises(ValueError, match="Key must be hex"):
        Cipher("not-a-hex-string-of-any-length--")

def test_encrypt_decrypt_roundtrip():
    cipher = Cipher(TEST_KEY_HEX)
    payload = {"action": "bootstrap", "aud": "wg0", "meta": {"foo": "bar"}}
    
    # Encrypt
    encrypted = cipher.encrypt(payload)
    
    assert encrypted["@type"] == "EncryptedResource"
    assert "ciphertext" in encrypted
    assert "nonce" in encrypted
    assert encrypted["ciphertext"] != json.dumps(payload) # Should involve change
    
    # Decrypt
    decrypted = cipher.decrypt(encrypted)
    assert decrypted == payload

def test_decrypt_invalid_key_fails():
    cipher1 = Cipher(TEST_KEY_HEX)
    # Different key
    cipher2 = Cipher("ff" * 32)
    
    payload = {"secret": "data"}
    encrypted = cipher1.encrypt(payload)
    
    with pytest.raises(CryptoError, match="Decryption failed"):
        cipher2.decrypt(encrypted)

def test_decrypt_tampered_ciphertext_fails():
    cipher = Cipher(TEST_KEY_HEX)
    encrypted = cipher.encrypt({"foo": "bar"})
    
    # Tamper with ciphertext
    import base64
    ct = base64.b64decode(encrypted["ciphertext"])
    tampered_ct = bytearray(ct)
    tampered_ct[0] ^= 0xFF # Flip a bit
    encrypted["ciphertext"] = base64.b64encode(tampered_ct).decode("utf-8")
    
    with pytest.raises(CryptoError, match="Decryption failed"):
        cipher.decrypt(encrypted)
