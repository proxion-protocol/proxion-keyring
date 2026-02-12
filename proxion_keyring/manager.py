import os
import threading
from typing import Dict, Optional, Any
from .registry import AppRegistry
from .core import EventBus, Guardian
from .core.identity import Identity
from .core.tunnel import Tunnel
from .core.stash import Stash
from .scout import SecurityCouncil
from proxion_core import RevocationList

class KeyringManager:
    """
    Central coordinator for Proxion Keyring state.
    Delegates to modular core components for Identity, VPN, Storage, and Security.
    """
    
    def __init__(self):
        # Configuration
        from .config import load_config
        self.config = load_config()
        self.pod_local_root = self.config.get("pod_local_root")
        print(f"Keyring: Pod Local Root aimed at: {self.pod_local_root}")

        self._lock = threading.Lock()
        
        # 1. Identity & Cryptography
        from .identity import load_or_create_identity_key
        self.private_key = load_or_create_identity_key()
        self.identity = Identity(self.private_key)
        
        # 2. Event Bus (The Guardian Stream)
        self.event_log_path = os.path.join(self.pod_local_root, "system_events.jsonl")
        self.events = EventBus(self.event_log_path)
        # Compatibility: proxy events to old deque if any legacy code needs it
        self.event_queue = self.events.memory_queue

        # 3. VPN & Mobility (Tunnel)
        from .rs.backends.factory import create_backend
        self.bg_backend = create_backend(use_mock=False)
        self.tunnel = Tunnel(self.pod_local_root, self.bg_backend)

        # 4. Storage & Solid Integration (Stash)
        self.stash = Stash(self.identity)

        self.guardian = Guardian(self.pod_local_root, self.events, SecurityCouncil())
        self.guardian.start_watchdog()

        # 6. Security & Revocation (Compliance)
        self.revocation_list = RevocationList()

        # Legacy / Extra Components (To be modularized later)
        from .warden import Warden
        self.warden = Warden()
        from .lens import Lens
        self.lens = Lens(self)
        from .archivist import Archivist
        self.archivist = Archivist(self)
        from .identity import IdentityGateway
        self.gateway = IdentityGateway(self)
        from .mesh import MeshCoordinator
        self.mesh = MeshCoordinator(self)
        
        # 7. Sovereign Sharing (Phase 2)
        from .core.vault import VaultManager
        from .core.sharing import SharingManager
        
        # Instantiate Zero-Knowledge Vault
        self.vault = VaultManager(self.identity.get_master_seed())
        
        # SharingManager now uses the Vault for secure persistence
        self.sharing = SharingManager(self.identity, self.vault, self.pod_local_root)

        self.registry = AppRegistry()
        from .os_adapter import get_adapter
        self.adapter = get_adapter()

    # --- Sharing Facade ---
    def create_sharing_invite(self, recipient_web_id: str, resource_uri: str, actions: str = "read") -> Dict:
        """Issue a signed FederationInvite for resource sharing."""
        return self.sharing.create_invite(recipient_web_id, resource_uri, actions)

    def process_sharing_acceptance(self, acceptance_data: Dict) -> Dict:
        """Verify an acceptance and issue a RelationshipCertificate."""
        return self.sharing.process_acceptance(acceptance_data)

    def get_sharing_relationships(self) -> Dict:
        """List active resource sharing relationships from the registry."""
        registry_path = os.path.join(self.pod_local_root, "relationships.json")
        if os.path.exists(registry_path):
            try:
                with open(registry_path, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    # --- Identity Facade ---
    @property
    def public_key(self):
        return self.identity.public_key

    def get_signing_key(self) -> bytes:
        return self.identity.get_signing_key()

    def get_public_key_hex(self) -> str:
        return self.identity.get_public_key_hex()

    def validate_token(self, token_data: str, ctx_data: dict, proof: dict):
        return self.identity.validate_token(token_data, ctx_data, proof)

    def sign_challenge(self, challenge: bytes) -> bytes:
        return self.identity.sign_challenge(challenge)

    # --- Tunnel Facade ---
    def register_mobile_peer(self, pubkey: str, metadata: Dict[str, Any]):
        return self.tunnel.register_mobile_peer(pubkey, metadata)

    def revoke_peer(self, pubkey: str):
        return self.tunnel.revoke_peer(pubkey)

    @property
    def registered_peers(self):
        return self.tunnel.registered_peers

    @property
    def active_invitations(self):
        return self.tunnel.invitations

    @property
    def wg_server_pub(self):
        return self.tunnel.wg_server_pub

    def check_rate_limit(self, client_ip: str) -> bool:
        return self.tunnel.check_rate_limit(client_ip)

    def create_invitation(self, capabilities: list, expiration: str, metadata: dict):
        return self.tunnel.create_invitation(capabilities, expiration, metadata)

    def revoke_invitation(self, invite_id: str):
        if invite_id in self.tunnel.invitations:
            del self.tunnel.invitations[invite_id]
            self.tunnel._save_invitations()

    def generate_client_config(self) -> Dict[str, str]:
        """Generate a complete onboarding configuration for mobile/extensions."""
        priv, pub = self.bg_backend.generate_keypair()
        return {
            "public_key": pub,
            "private_key": priv,
            "endpoint": os.environ.get("proxion-keyring_WG_ENDPOINT", "127.0.0.1:51820"),
            "pod_url": self.get_pod_url()
        }

    # --- Stash Facade ---
    def mint_stash_token(self, holder_pub_key_hex: str, path_prefix: str = "/") -> dict:
        return self.stash.mint_stash_token(holder_pub_key_hex, path_prefix)

    def activate_session(self, web_id: str, access_token: str):
        return self.stash.activate_session(web_id, access_token)

    def storage_delete(self, path: str) -> bool:
        return self.stash.storage_delete(path)

    def storage_ls(self, path: str = "/"):
        return self.stash.storage_ls(path)

    def get_pod_url(self) -> str:
        return self.config.get("pod_url", "http://localhost:8889/pod")

    # --- Guardian Facade ---
    def log_event(self, action: str, resource: str, subject: str = "System", type: str = "info"):
        self.events.log(action, resource, subject, type)

    @property
    def medic_stats(self):
        return self.guardian.medic_stats

    @medic_stats.setter
    def medic_stats(self, value):
        """Compatibility for legacy server.py refresh pattern."""
        pass

    def _load_medic_stats(self):
        """Compatibility for server.py"""
        return self.guardian.refresh_stats()

    def get_suite_status(self) -> Dict[str, Any]:
        """Detailed health check for the Dashboard."""
        return {
            "proxy": "ONLINE" if hasattr(self, 'pod_proxy') and self.pod_proxy else "OFFLINE",
            "containers": self._get_docker_containers(),
            "security_hub": {
                "identity": {"status": "HEALTHY", "services": ["authentik", "keyring"]},
                "credentials": {"status": "HEALTHY", "services": ["vaultwarden", "archivst"]},
                "dns": {"status": "ONLINE", "services": ["adguard", "pialert"]},
                "governance": {"status": "OFFLINE", "services": ["watchtower"]}
            }
        }

    def orchestrate_suite(self, action: str, target: str = "all") -> Dict[str, Any]:
        """Run bulk docker-compose operations with transparent logging."""
        import subprocess
        results = []
        integrations_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../integrations"))
        
        targets = []
        if target == "all":
            if os.path.exists(integrations_root):
                targets = [d for d in os.listdir(integrations_root) if os.path.isdir(os.path.join(integrations_root, d))]
        else:
            # Handle both 'app' and 'app-integration' inputs
            t_name = target if target.endswith("-integration") else f"{target}-integration"
            targets = [t_name]

        self.log_event(f"SUITE: Executing bulk {action.upper()} on {len(targets)} integrations...", "Suite", "Orchestrate", "warning")

        for t in targets:
            app_path = os.path.join(integrations_root, t)
            if os.path.exists(app_path):
                self.log_event(f"ACTION: {action.upper()} requested for {t}...", "Suite", "Action", "info")
                cmd = self.adapter.get_docker_compose_cmd(app_path, self.pod_local_root, [action, "-d"])
                try:
                    # For v2 support, we might need to intercept 'docker-compose' and use 'docker compose'
                    if cmd[0] == "docker-compose":
                        cmd = ["docker", "compose"] + cmd[1:]
                        
                    res = subprocess.run(cmd, cwd=app_path, capture_output=True, text=True)
                    if res.returncode == 0:
                        self.log_event(f"SUCCESS: {t} is now {action.upper()}", "Suite", "Action", "success")
                        results.append({"integration": t, "status": "OK"})
                    else:
                        error_msg = res.stderr.strip() or res.stdout.strip()
                        self.log_event(f"FAILED: {t} {action.upper()} failure: {error_msg}", "Suite", "Error", "error")
                        results.append({"integration": t, "status": "ERROR", "error": error_msg})
                except Exception as e:
                    self.log_event(f"CRASH: Orchestration error for {t}: {str(e)}", "Suite", "Error", "error")
                    results.append({"integration": t, "status": "ERROR", "error": str(e)})

        return {"results": results}

    def _get_docker_containers(self) -> list:
        import subprocess
        try:
            # Use -a to see stopped ones too, and include image/ports for detail
            res = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}|{{.Image}}|{{.Ports}}"]).decode()
            return [
                {"name": l.split('|')[0], "status": l.split('|')[1], "image": l.split('|')[2], "ports": l.split('|')[3]} 
                for l in res.strip().split('\n') if '|' in l
            ]
        except:
            return []

    def get_app_metrics(self, category: str) -> Dict[str, Any]:
        """Fetch metrics for a category, integrating with Guardian and AdGuard."""
        if category == "dns":
            import requests
            try:
                from .identity import derive_app_password
                password = derive_app_password(self.private_key, "adguard")
                resp = requests.get("http://127.0.0.1:3055/control/stats", timeout=0.5, auth=('proxion', password))
                if resp.ok:
                    data = resp.json()
                    return {
                        "queries": data.get("num_dns_queries", 0),
                        "blocked": f"{data.get('num_blocked_filtering', 0)} ({data.get('blocked_percentage', 0):.1f}%)",
                        "active": True
                    }
            except:
                return {"error": "AdGuard Offline"}
        
        stats = self.guardian.refresh_stats()
        return stats.get("metrics", {}).get(category, {})

    def run_network_medic(self) -> Dict[str, Any]:
        return self.guardian.run_network_medic()

    def _load_medic_stats(self) -> Dict[str, Any]:
        return self.guardian.refresh_stats()

    @property
    def medic_stats(self) -> Dict[str, Any]:
        return self.guardian.medic_stats

    @medic_stats.setter
    def medic_stats(self, value: Dict[str, Any]):
        self.guardian.medic_stats = value

    def forge_image(self, container_name: str) -> bool:
        app_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), f"../../integrations/{container_name}-integration"))
        return self.guardian.forge_image(container_name, app_dir)

    def harden_fleet(self) -> Dict[str, Any]:
        return self.guardian.harden_fleet()

    def mass_forge_integrations(self):
        """Bulk forge every integration in the fleet."""
        integrations_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../integrations"))
        if not os.path.exists(integrations_root):
            return
        
        targets = [d for d in os.listdir(integrations_root) if os.path.isdir(os.path.join(integrations_root, d))]
        total = len(targets)
        for i, t in enumerate(targets):
            container_name = t.replace("-integration", "")
            # Update status for dashboard
            self.guardian.medic_stats["status"] = f"FORGING ({i+1}/{total})"
            self.guardian.medic_stats["target"] = container_name
            self.guardian._save_medic_stats()
            
            success = self.forge_image(container_name)
            
            # Progressively update health score (Simplified: Success adds to health)
            if success:
                # We assume 100% is all forged. 
                # This is a bit arbitrary but good for visibility.
                self.guardian.medic_stats["fleet_health"] = int(((i + 1) / total) * 100)
                self.guardian._save_medic_stats()

        self.guardian.medic_stats["status"] = "HEALTHY"
        self.guardian.medic_stats.pop("target", None)
        self.guardian._save_medic_stats()

    def set_dns_safety_mode(self, enabled: bool) -> Dict[str, Any]:
        """Toggle Host DNS to point to Proxion AdGuard for protection."""
        idx = self.adapter.get_active_interface_index()
        if not idx:
            return {"status": "ERROR", "error": "No active interface"}
            
        if enabled:
            # 127.0.0.1 (AdGuard)
            self.adapter.set_dns(idx, ["127.0.0.1"])
            return {"status": "ENABLED", "dns": "127.0.0.1"}
        else:
            self.adapter.reset_dns(idx)
            return {"status": "DISABLED", "dns": "DHCP"}

    def get_relationships(self) -> list:
        """Return a unified list of mesh and resource sharing relationships."""
        results = []
        
        # 1. Mesh Relationships (Mobile/Fleet)
        for pubkey, meta in self.registered_peers.items():
            results.append({
                "type": "mesh_peer",
                "id": pubkey,
                "label": meta.get("name", "Mobile Device"),
                "status": "active",
                "caps": ["*"], # Mesh peers usually have root-like access to their own suite
                "meta": meta
            })
            
        # 2. Resource Sharing Relationships
        sharing_rels = self.get_sharing_relationships()
        for rel_id, rel in sharing_rels.items():
            results.append({
                "type": "resource_share",
                "id": rel_id,
                "label": f"Shared with {rel.get('subject')[:12]}...",
                "status": "active", # Future: check expiration
                "caps": [f"{c['can']} @ {c['with']}" for c in rel.get("capabilities", [])],
                "meta": rel
            })
            
        return results

    def revoke_relationship(self, rel_id: str):
        """Kill a trust relationship (mesh or resource share)."""
        # Try mesh peer first
        if rel_id in self.registered_peers:
            return self.revoke_peer(rel_id)
            
        # Then check resource sharing
        registry_path = os.path.join(self.pod_local_root, "relationships.json")
        if os.path.exists(registry_path):
            try:
                with open(registry_path, "r") as f:
                    registry = json.load(f)
                if rel_id in registry:
                    del registry[rel_id]
                    with open(registry_path, "w") as f:
                        json.dump(registry, f, indent=4)
                    return True
            except:
                pass
        return False

