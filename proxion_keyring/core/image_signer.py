import subprocess
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

class ImageSigner:
    """V7.9: Cryptographic image signing and verification using Cosign."""
    
    def __init__(self, pod_local_root: str):
        self.pod_local_root = pod_local_root
        self.key_path = os.path.join(pod_local_root, "cosign.key")
        self.pub_key_path = os.path.join(pod_local_root, "cosign.pub")
        self._ensure_keys()
    
    def _ensure_keys(self):
        """Generate Cosign keypair if not exists."""
        if not os.path.exists(self.key_path):
            print("ImageSigner: Generating Cosign keypair...")
            try:
                # Generate keypair (non-interactive with empty password)
                subprocess.run([
                    "cosign", "generate-key-pair",
                    "--output-key-prefix", os.path.join(self.pod_local_root, "cosign")
                ], env={**os.environ, "COSIGN_PASSWORD": ""}, check=True)
                print(f"ImageSigner: Keys generated at {self.pod_local_root}")
            except FileNotFoundError:
                print("ImageSigner: WARNING - Cosign not installed. Image signing disabled.")
            except Exception as e:
                print(f"ImageSigner: Key generation failed: {e}")
    
    def sign_image(self, image_name: str) -> Dict[str, Any]:
        """Sign a Docker image with Cosign, handling local-only naming issues."""
        if not os.path.exists(self.key_path):
            return {"status": "SKIPPED", "reason": "No signing key available"}
        
        # V7.12: Prevent registry authentication errors for local-only images
        # Images without a '/' are typically interpreted by cosign as 'library/repo', 
        # which usually requires ownership of the repo on Docker Hub.
        if "/" not in image_name:
            return {
                "status": "SKIPPED", 
                "reason": f"Image '{image_name}' is not namespaced. Cosign requires a registry 'user/repo' format to store signatures (e.g. youruser/{image_name})."
            }

        try:
            # We add --allow-import-os-alias just in case, but standard registry signing is preferred
            res = subprocess.run([
                "cosign", "sign", "--key", self.key_path,
                "--yes",  # Skip confirmation
                image_name
            ], capture_output=True, env={**os.environ, "COSIGN_PASSWORD": ""}, timeout=60)
            
            if res.returncode == 0:
                return {
                    "status": "SIGNED",
                    "image": image_name,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                stderr = res.stderr.decode()
                if "UNAUTHORIZED" in stderr:
                    return {
                        "status": "FAILED",
                        "error": "Registry authentication failed. Do you own this repository on the registry?"
                    }
                return {
                    "status": "FAILED",
                    "error": stderr
                }
        except FileNotFoundError:
            return {"status": "SKIPPED", "reason": "Cosign not installed"}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
    
    def verify_image(self, image_name: str) -> Dict[str, Any]:
        """Verify image signature."""
        if not os.path.exists(self.pub_key_path):
            return {"status": "SKIPPED", "reason": "No public key available"}
        
        try:
            res = subprocess.run([
                "cosign", "verify", "--key", self.pub_key_path,
                image_name
            ], capture_output=True, timeout=60)
            
            if res.returncode == 0:
                return {
                    "status": "VERIFIED",
                    "image": image_name,
                    "valid": True
                }
            else:
                return {
                    "status": "INVALID",
                    "image": image_name,
                    "valid": False,
                    "error": res.stderr.decode()
                }
        except FileNotFoundError:
            return {"status": "SKIPPED", "reason": "Cosign not installed"}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
