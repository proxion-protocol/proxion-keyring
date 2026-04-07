import requests
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

class InfisicalManager:
    """
    Interfaces with an Infisical instance for sovereign secret management.
    Supports fetching environment-specific secrets (e.g., Headscale keys, VPN creds).
    """
    
    def __init__(self, site_url: str, client_id: str, client_secret: str):
        self.site_url = site_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token: Optional[str] = None

    def _authenticate(self) -> bool:
        """Fetch an access token using Universal Auth (Machine Identity)."""
        try:
            resp = requests.post(
                f"{self.site_url}/api/v1/auth/universal-auth/login",
                json={
                    "clientId": self.client_id,
                    "clientSecret": self.client_secret
                }
            )
            if resp.status_code == 200:
                self._access_token = resp.json().get("accessToken")
                return True
            logger.error(f"Infisical: Auth failed: {resp.text}")
        except Exception as e:
            logger.error(f"Infisical: Auth request failed: {e}")
        return False

    def get_secret(self, secret_name: str, workspace_id: str, environment: str = "prod") -> Optional[str]:
        """Retrieve a secret by name."""
        if not self._access_token and not self._authenticate():
            return None
            
        try:
            resp = requests.get(
                f"{self.site_url}/api/v3/secrets/raw/{secret_name}",
                headers={"Authorization": f"Bearer {self._access_token}"},
                params={
                    "workspaceId": workspace_id,
                    "environment": environment
                }
            )
            if resp.status_code == 200:
                return resp.json().get("secret", {}).get("secretValue")
            
            # If 401, token might have expired
            if resp.status_code == 401:
                self._access_token = None
                return self.get_secret(secret_name, workspace_id, environment)
                
            logger.error(f"Infisical: Secret fetch failed ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"Infisical: Secret request failed: {e}")
        return None

    def get_all_secrets(self, workspace_id: str, environment: str = "prod") -> Dict[str, str]:
        """Fetch all secrets for a specific workspace/environment."""
        if not self._access_token and not self._authenticate():
            return {}
            
        try:
            resp = requests.get(
                f"{self.site_url}/api/v3/secrets/raw",
                headers={"Authorization": f"Bearer {self._access_token}"},
                params={
                    "workspaceId": workspace_id,
                    "environment": environment
                }
            )
            if resp.status_code == 200:
                secrets = resp.json().get("secrets", [])
                return {s["secretKey"]: s["secretValue"] for s in secrets}
        except Exception as e:
            logger.error(f"Infisical: Bulk fetch failed: {e}")
        return {}
