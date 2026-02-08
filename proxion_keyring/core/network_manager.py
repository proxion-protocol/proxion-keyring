import subprocess
import os
from typing import Dict, List, Any

class NetworkManager:
    """V7.6: Manage tiered security networks for container isolation."""
    
    SECURITY_TIERS = {
        "public": ["adguard", "nginx", "traefik"],  # Internet-facing
        "internal": ["vaultwarden", "calibre", "archivebox"],  # Internal services
        "admin": ["keyring", "authentik", "watchtower"]  # Admin/management
    }
    
    def __init__(self):
        self.networks_created = False
    
    def create_security_networks(self) -> Dict[str, Any]:
        """Create tiered Docker networks."""
        results = {}
        
        for tier in ["public", "internal", "admin"]:
            try:
                res = subprocess.run([
                    "docker", "network", "create",
                    "--driver", "bridge",
                    "--label", f"proxion.tier={tier}",
                    tier
                ], capture_output=True)
                
                if res.returncode == 0 or "already exists" in res.stderr.decode():
                    results[tier] = "CREATED" if res.returncode == 0 else "EXISTS"
                else:
                    results[tier] = f"FAILED: {res.stderr.decode()}"
            except Exception as e:
                results[tier] = f"ERROR: {str(e)}"
        
        self.networks_created = all(v in ["CREATED", "EXISTS"] for v in results.values())
        return results
    
    def assign_container_to_tier(self, container_name: str) -> str:
        """Determine which tier a container belongs to."""
        for tier, containers in self.SECURITY_TIERS.items():
            if container_name in containers:
                return tier
        return "internal"  # Default to internal tier
    
    def connect_container_to_tier(self, container_name: str, tier: str) -> bool:
        """Connect a running container to its security tier network."""
        try:
            # Disconnect from default bridge
            subprocess.run([
                "docker", "network", "disconnect", "bridge", container_name
            ], capture_output=True, check=False)
            
            # Connect to tier network
            res = subprocess.run([
                "docker", "network", "connect", tier, container_name
            ], capture_output=True)
            
            return res.returncode == 0
        except Exception:
            return False
    
    def audit_network_segmentation(self) -> Dict[str, Any]:
        """Audit current network assignments."""
        results = {
            "compliant": [],
            "non_compliant": [],
            "unassigned": []
        }
        
        try:
            # Get all running containers
            res = subprocess.check_output([
                "docker", "ps", "--format", "{{.Names}}"
            ]).decode().strip().split("\n")
            
            for container in res:
                if not container:
                    continue
                    
                # Get container's networks
                networks = subprocess.check_output([
                    "docker", "inspect", container,
                    "--format", "{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}"
                ]).decode().strip().split()
                
                expected_tier = self.assign_container_to_tier(container)
                
                if expected_tier in networks:
                    results["compliant"].append({
                        "container": container,
                        "tier": expected_tier
                    })
                elif "bridge" in networks:
                    results["non_compliant"].append({
                        "container": container,
                        "expected_tier": expected_tier,
                        "actual": "bridge"
                    })
                else:
                    results["unassigned"].append(container)
        
        except Exception as e:
            results["error"] = str(e)
        
        return results
