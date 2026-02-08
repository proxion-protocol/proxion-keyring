"""
V7.17: Air-Gapped Forge Environment

This module provides utilities for building images in an isolated Docker context
to prevent supply chain attacks during the build process.
"""

import subprocess
import os
from typing import Dict, Any, Optional

class AirGappedForge:
    """Manage air-gapped Docker context for secure builds."""
    
    def __init__(self, context_name: str = "forge-isolated"):
        self.context_name = context_name
        self.context_exists = False
        self._check_context()
    
    def _check_context(self):
        """Check if isolated context exists."""
        try:
            res = subprocess.run([
                "docker", "context", "ls", "--format", "{{.Name}}"
            ], capture_output=True, text=True)
            
            self.context_exists = self.context_name in res.stdout
        except Exception:
            self.context_exists = False
    
    def create_isolated_context(self, docker_host: str = "tcp://localhost:2376") -> bool:
        """Create isolated Docker context."""
        try:
            if self.context_exists:
                print(f"AirGappedForge: Context '{self.context_name}' already exists.")
                return True
            
            res = subprocess.run([
                "docker", "context", "create", self.context_name,
                "--docker", f"host={docker_host}"
            ], capture_output=True)
            
            if res.returncode == 0:
                self.context_exists = True
                print(f"AirGappedForge: Created isolated context '{self.context_name}'")
                return True
            else:
                print(f"AirGappedForge: Failed to create context: {res.stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"AirGappedForge: Error creating context: {e}")
            return False
    
    def build_in_isolated_context(self, build_path: str, image_name: str) -> Dict[str, Any]:
        """Build image in isolated context."""
        if not self.context_exists:
            return {"status": "ERROR", "error": "Isolated context does not exist"}
        
        try:
            # Switch to isolated context
            subprocess.run(["docker", "context", "use", self.context_name], check=True)
            
            # Build image
            res = subprocess.run([
                "docker", "build", "-t", image_name, build_path
            ], capture_output=True)
            
            # Switch back to default context
            subprocess.run(["docker", "context", "use", "default"], check=False)
            
            if res.returncode == 0:
                return {
                    "status": "SUCCESS",
                    "image": image_name,
                    "context": self.context_name
                }
            else:
                return {
                    "status": "FAILED",
                    "error": res.stderr.decode()
                }
                
        except Exception as e:
            # Ensure we switch back to default
            subprocess.run(["docker", "context", "use", "default"], check=False)
            return {"status": "ERROR", "error": str(e)}
    
    def export_image_to_default_context(self, image_name: str) -> bool:
        """Export image from isolated context to default context."""
        try:
            # Save image to tar
            temp_tar = f"/tmp/{image_name.replace('/', '_')}.tar"
            
            subprocess.run(["docker", "context", "use", self.context_name], check=True)
            subprocess.run(["docker", "save", "-o", temp_tar, image_name], check=True)
            
            # Load into default context
            subprocess.run(["docker", "context", "use", "default"], check=True)
            subprocess.run(["docker", "load", "-i", temp_tar], check=True)
            
            # Cleanup
            os.remove(temp_tar)
            
            print(f"AirGappedForge: Exported {image_name} to default context")
            return True
            
        except Exception as e:
            subprocess.run(["docker", "context", "use", "default"], check=False)
            print(f"AirGappedForge: Export failed: {e}")
            return False
