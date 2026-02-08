"""
V7.15: Immutable Infrastructure Template Generator

This module generates hardened docker-compose configurations with:
- Read-only root filesystems
- Tmpfs mounts for writable paths
- Dropped capabilities
- Non-root users
"""

import os
import yaml
from typing import Dict, Any, List

class ImmutableInfrastructure:
    """Generate immutable container configurations."""
    
    COMMON_WRITABLE_PATHS = [
        "/tmp",
        "/var/run",
        "/var/tmp",
        "/var/cache"
    ]
    
    def apply_immutability(self, compose_path: str) -> bool:
        """Apply immutability constraints to docker-compose.yml."""
        try:
            with open(compose_path, "r") as f:
                compose = yaml.safe_load(f)
            
            # Apply to all services
            for service_name, service_config in compose.get("services", {}).items():
                # V7.15: Read-only root filesystem
                service_config["read_only"] = True
                
                # Add tmpfs for writable paths
                if "tmpfs" not in service_config:
                    service_config["tmpfs"] = []
                
                for path in self.COMMON_WRITABLE_PATHS:
                    if path not in service_config["tmpfs"]:
                        service_config["tmpfs"].append(path)
                
                # V7.16: Drop all capabilities by default
                if "cap_drop" not in service_config:
                    service_config["cap_drop"] = ["ALL"]
                
                # Only add back essential capabilities
                if "cap_add" not in service_config:
                    service_config["cap_add"] = []
                
                # Add NET_BIND_SERVICE if ports are exposed
                if service_config.get("ports") and "NET_BIND_SERVICE" not in service_config["cap_add"]:
                    service_config["cap_add"].append("NET_BIND_SERVICE")
            
            # Write back
            backup_path = compose_path + ".pre-immutable"
            os.rename(compose_path, backup_path)
            
            with open(compose_path, "w") as f:
                yaml.dump(compose, f, default_flow_style=False)
            
            print(f"ImmutableInfra: Applied immutability to {compose_path}")
            print(f"ImmutableInfra: Backup saved to {backup_path}")
            return True
            
        except Exception as e:
            print(f"ImmutableInfra: Failed to apply immutability: {e}")
            return False
    
    def generate_dockerfile_with_nonroot_user(self, base_dockerfile: str, output_path: str) -> bool:
        """V7.16: Add non-root user to Dockerfile."""
        try:
            with open(base_dockerfile, "r") as f:
                lines = f.readlines()
            
            # Find the last FROM statement
            last_from_idx = 0
            for i, line in enumerate(lines):
                if line.strip().startswith("FROM"):
                    last_from_idx = i
            
            # Insert user creation after last FROM
            user_lines = [
                "\n# V7.16: Run as non-root user\n",
                "RUN adduser -D -u 1000 proxion\n",
                "USER proxion\n"
            ]
            
            lines = lines[:last_from_idx+1] + user_lines + lines[last_from_idx+1:]
            
            with open(output_path, "w") as f:
                f.writelines(lines)
            
            print(f"ImmutableInfra: Generated non-root Dockerfile at {output_path}")
            return True
            
        except Exception as e:
            print(f"ImmutableInfra: Failed to generate non-root Dockerfile: {e}")
            return False
