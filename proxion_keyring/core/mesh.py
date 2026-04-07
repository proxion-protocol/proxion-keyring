import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class HeadscaleManager:
    """
    Automates enrollment and management of nodes in a Headscale (Tailscale) mesh.
    Ensures each Proxion node has a secure, authenticated IP on the global backbone.
    """
    
    def __init__(self, api_url: str, api_key: str, namespace: str = "proxion"):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.namespace = namespace

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def generate_preauth_key(self, ephemeral: bool = True, reusable: bool = False) -> Optional[str]:
        """Generate a pre-auth key for a new node to join the mesh."""
        try:
            resp = requests.post(
                f"{self.api_url}/api/v1/preauthkey",
                headers=self._get_headers(),
                json={
                    "user": self.namespace,
                    "reusable": reusable,
                    "ephemeral": ephemeral,
                    "expiration": "24h"
                }
            )
            if resp.status_code == 200:
                return resp.json().get("key")
            logger.error(f"Headscale: Failed to generate pre-auth key: {resp.text}")
        except Exception as e:
            logger.error(f"Headscale: Request failed: {e}")
        return None

    def register_node(self, machine_key: str) -> bool:
        """Manually register a node if pre-auth is not used."""
        try:
            resp = requests.post(
                f"{self.api_url}/api/v1/machine/{machine_key}/register?user={self.namespace}",
                headers=self._get_headers()
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Headscale: Registration failed: {e}")
        return False

    def get_node_status(self, hostname: str) -> Optional[Dict[str, Any]]:
        """Fetch status for a specific node in the mesh."""
        try:
            resp = requests.get(
                f"{self.api_url}/api/v1/node",
                headers=self._get_headers()
            )
            if resp.status_code == 200:
                nodes = resp.json().get("nodes", [])
                for node in nodes:
                    if node.get("givenName") == hostname:
                        return node
        except Exception as e:
            logger.error(f"Headscale: Status fetch failed: {e}")
        return None

class MeshCoordinator:
    """
    Orchestrates the connectivity lifecycle for a Proxion node.
    Combines Identity, Headscale, and VPN logic.
    """
    
    def __init__(self, keyring_manager):
        self.keyring = keyring_manager
        self.headscale = None # Initialized on demand with creds
        
    def bootstrap_mesh(self, config: Dict[str, str]):
        """Initialize Headscale with provided configuration."""
        self.headscale = HeadscaleManager(
            api_url=config.get("api_url"),
            api_key=config.get("api_key"),
            namespace=config.get("namespace", "proxion")
        )
        logger.info("MeshCoordinator: Headscale adapter initialized.")

    def enroll_local_node(self):
        """Perform automated enrollment of the current host."""
        if not self.headscale:
            logger.warning("MeshCoordinator: Headscale not configured. Skipping enrollment.")
            return False
            
        # Logic to trigger 'tailscale up --login-server ...' would happen here via OS adapter
        logger.info("MeshCoordinator: Initiating Headscale enrollment sequence.")
        return True
