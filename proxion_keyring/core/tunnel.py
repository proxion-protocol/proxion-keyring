import os
import json
import time
import yaml
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timezone

class Tunnel:
    """WireGuard and Mobile Onboarding management."""
    
    def __init__(self, pod_local_root: str, backend):
        self.pod_local_root = pod_local_root
        self.backend = backend
        self.peers_path = os.path.join(self.pod_local_root, "peers.json")
        self.invites_path = os.path.join(self.pod_local_root, "invitations.json")
        
        self.registered_peers: Dict[str, Dict] = self._load_peers()
        self.invitations: Dict[str, Dict] = self._load_invitations()
        self.rate_limits: Dict[str, list] = {} # ip -> [timestamps]

        self.wg_server_priv: Optional[str] = None
        self.wg_server_pub: Optional[str] = None
        self._ensure_wireguard_keys()

    def _ensure_wireguard_keys(self):
        """Ensure persistent WireGuard identity exists."""
        key_file = os.path.join(self.pod_local_root, "wg_server.key")
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                self.wg_server_priv = f.read().strip()
        else:
            # Generate new keypair via backend
            if hasattr(self.backend, "generate_keypair"):
                self.wg_server_priv, _ = self.backend.generate_keypair()
            else:
                # Fallback / Mock
                self.wg_server_priv = "DUMMY_PRIVATE_KEY"
                
            with open(key_file, "w") as f:
                f.write(self.wg_server_priv)
        
        if hasattr(self.backend, "get_public_from_private"):
            self.wg_server_pub = self.backend.get_public_from_private(self.wg_server_priv)
        else:
            self.wg_server_pub = "DUMMY_PUBLIC_KEY"

    def register_mobile_peer(self, pubkey: str, metadata: Dict[str, Any]):
        """Track a registered device for revocation."""
        self.registered_peers[pubkey] = {
            "registered_at": datetime.now(timezone.utc).isoformat(),
            **metadata
        }
        self._save_peers()

    def revoke_peer(self, pubkey: str):
        """Kill switch for a specific mobile peer."""
        if pubkey in self.registered_peers:
            del self.registered_peers[pubkey]
            self._save_peers()
            # Actual WireGuard removal logic would go here
            return True
        return False

    def _save_peers(self):
        try:
            with open(self.peers_path, "w") as f:
                json.dump(self.registered_peers, f, indent=2)
        except Exception as e:
            print(f"Tunnel: Failed to save peers: {e}")

    def _load_peers(self):
        if os.path.exists(self.peers_path):
            try:
                with open(self.peers_path, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def _load_invitations(self):
        if os.path.exists(self.invites_path):
            try:
                with open(self.invites_path, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def _save_invitations(self):
        try:
            with open(self.invites_path, "w") as f:
                json.dump(self.invitations, f, indent=2)
        except Exception as e:
            print(f"Tunnel: Failed to save invitations: {e}")

    def create_invitation(self, capabilities: list, expiration_delta: str, metadata: dict):
        import uuid
        invite_id = str(uuid.uuid4())
        self.invitations[invite_id] = {
            "capabilities": capabilities,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata,
            "used": False
        }
        self._save_invitations()
        return invite_id

    def check_rate_limit(self, client_ip: str) -> bool:
        now = time.time()
        timestamps = self.rate_limits.get(client_ip, [])
        # Cleanup old
        timestamps = [t for t in timestamps if now - t < 3600]
        if len(timestamps) >= 5:
            return False
        timestamps.append(now)
        self.rate_limits[client_ip] = timestamps
        return True

class TunnelManager:
    """
    Manages modular VPN sidecars (Gluetun) for Proxion integrations.
    Ensures that containers are isolated and only communicate through the VPN.
    """
    
    def __init__(self, integrations_root: str, vault_manager=None):
        self.integrations_root = integrations_root
        self.vault = vault_manager
        
    def get_vpn_config(self) -> Dict[str, Any]:
        """Retrieve VPN credentials from the vault."""
        if not self.vault:
            return {
                "VPN_SERVICE_PROVIDER": "custom",
                "VPN_TYPE": "wireguard",
                "WIREGUARD_PRIVATE_KEY": "FIXME_REPLACE_WITH_VAULT_KEY",
                "WIREGUARD_ADDRESSES": "10.0.0.2/32"
            }
        
        creds = self.vault.secure_load(os.path.join(os.path.dirname(self.integrations_root), "stash", "vault"), "vpn_creds")
        if not creds:
             logging.warning("TunnelManager: No vpn_creds found in vault.")
             return {
                "VPN_SERVICE_PROVIDER": "custom",
                "VPN_TYPE": "wireguard",
                "WIREGUARD_PRIVATE_KEY": "FIXME_REPLACE_WITH_VAULT_KEY",
                "WIREGUARD_ADDRESSES": "10.0.0.2/32"
            }
        return creds

    def generate_override(self, integration_name: str) -> str:
        """Produce a docker-compose.override.yml that injects Gluetun."""
        vpn_config = self.get_vpn_config()
        app_name = integration_name.replace("-integration", "")
        
        override = {
            "version": "3",
            "services": {
                "gluetun": {
                    "image": "qmcgaw/gluetun",
                    "container_name": f"gluetun-{integration_name}",
                    "cap_add": ["NET_ADMIN"],
                    "devices": ["/dev/net/tun:/dev/net/tun"],
                    "environment": [
                        f"VPN_SERVICE_PROVIDER={vpn_config.get('VPN_SERVICE_PROVIDER', 'mullvad')}",
                        f"VPN_TYPE={vpn_config.get('VPN_TYPE', 'wireguard')}",
                        f"WIREGUARD_PRIVATE_KEY={vpn_config.get('WIREGUARD_PRIVATE_KEY', '')}",
                        f"WIREGUARD_ADDRESSES={vpn_config.get('WIREGUARD_ADDRESSES', '')}",
                        "HTTPPROXY=on",
                        "SHADOWSOCKS=on",
                    ],
                    "restart": "unless-stopped"
                },
                app_name: {
                    "network_mode": "service:gluetun",
                    "depends_on": ["gluetun"]
                }
            }
        }
        return yaml.dump(override, sort_keys=False)

    def enable_tunnel(self, integration_name: str) -> bool:
        """Apply the override to an integration."""
        target_dir = os.path.join(self.integrations_root, integration_name)
        if not os.path.exists(target_dir):
            return False
            
        override_content = self.generate_override(integration_name)
        override_path = os.path.join(target_dir, "docker-compose.override.yml")
        
        with open(override_path, "w") as f:
            f.write(override_content)
        return True

    def disable_tunnel(self, integration_name: str) -> bool:
        """Remove the override to restore standard networking."""
        target_dir = os.path.join(self.integrations_root, integration_name)
        override_path = os.path.join(target_dir, "docker-compose.override.yml")
        if os.path.exists(override_path):
            os.remove(override_path)
        return True

    def is_tunneled(self, integration_name: str) -> bool:
        """Check if an integration is currently configured for VPN."""
        target_dir = os.path.join(self.integrations_root, integration_name)
        return os.path.exists(os.path.join(target_dir, "docker-compose.override.yml"))
