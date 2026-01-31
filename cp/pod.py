import requests
from typing import Any, Optional
import json
from proxion_core.crypto import Cipher

class PodClient:
    """Lightweight client for interacting with a Solid Pod."""

    def __init__(self, pod_root: str, cipher: Optional[Cipher] = None):
        self.pod_root = pod_root.rstrip("/")
        self.cipher = cipher

    def get_resource(self, path: str, auth_token: Optional[str] = None) -> Any:
        """Fetch a JSON-LD resource from the Pod."""
        url = f"{self.pod_root}/{path.lstrip('/')}"
        headers = {
            "Accept": "application/ld+json"
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            # Transparent Decryption
            if self.cipher and isinstance(data, dict) and data.get("@type") == "EncryptedResource":
                try:
                    return self.cipher.decrypt(data)
                except Exception as e:
                    # If decryption fails, maybe return the raw data or raise?
                    # Raise is safer to avoid leaking ciphertext as plaintext expectation
                    raise RuntimeError(f"Failed to decrypt resource: {e}")
            return data
        elif response.status_code == 404:
            return None
        else:
            response.raise_for_status()

    def write_resource(self, path: str, data: Any, auth_token: str) -> bool:
        """Write a JSON-LD resource to the Pod."""
        url = f"{self.pod_root}/{path.lstrip('/')}"
        
        payload = data
        if self.cipher:
            payload = self.cipher.encrypt(data)
            
        headers = {
            "Content-Type": "application/ld+json",
            "Authorization": f"Bearer {auth_token}"
        }
        
        response = requests.put(url, data=json.dumps(payload), headers=headers)
        return response.status_code in [201, 204]

    def delete_resource(self, path: str, auth_token: str) -> bool:
        """Delete a resource from the Pod."""
        url = f"{self.pod_root}/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {auth_token}"
        }
        response = requests.delete(url, headers=headers)
        return response.status_code in [200, 204]
