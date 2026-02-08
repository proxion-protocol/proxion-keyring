from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from proxion_core.tokens import issue_token
from proxion_core.context import Caveat

class Stash:
    """Unified storage hub and Solid session management."""
    
    def __init__(self, identity):
        self.identity = identity
        self.sessions: Dict[str, Any] = {} # Active sessions
        self.pod_proxy = None # Injected later if needed

    def mint_stash_token(self, holder_pub_key_hex: str, path_prefix: str = "/") -> dict:
        """Mint a capability token for the Stash (FUSE) driver."""
        permissions = [("READ", "/"), ("WRITE", "/"), ("CREATE", "/"), ("DELETE", "/")]
        exp = datetime.now(timezone.utc) + timedelta(hours=24)
        
        caveats = []
        if path_prefix != "/":
            # Add attenuation caveat
            caveats.append(Caveat(f"path_prefix:{path_prefix}", lambda ctx: True)) 
        
        token = issue_token(
            permissions=permissions,
            exp=exp,
            aud=self.identity.get_public_key_hex(),
            caveats=caveats,
            holder_key_fingerprint=holder_pub_key_hex,
            signing_key=self.identity.get_signing_key()
        )
        return token.payload() | {"signature": token.signature}

    def activate_session(self, web_id: str, access_token: str):
        """Bridge the session from the frontend."""
        self.sessions[web_id] = {
            "access_token": access_token,
            "activated_at": datetime.now(timezone.utc).isoformat()
        }

    def get_auth_headers(self, url: str, method: str) -> Dict[str, str]:
        """Inject Solid OIDC tokens into outgoing requests."""
        # Note: In a full implementation, this would use DPoP with the identity key
        return {}

    def storage_delete(self, path: str) -> bool:
        """Delete a file or directory from the Unified Stash."""
        if self.pod_proxy:
             hub = self.pod_proxy.hub
             provider, subpath = hub._route(path)
             if provider and hasattr(provider, 'delete'):
                 return provider.delete(subpath)
        return False
    def storage_ls(self, path: str = "/") -> list:
        """List files/folders in the Unified Stash via HybridHub."""
        if not self.pod_proxy:
            return []
            
        hub = self.pod_proxy.hub
        entries = hub.list_dir(path)
        
        results = []
        for e in entries:
            full_path = "/".join([path.rstrip('/'), e]).replace("//", "/")
            attr = hub.get_attr(full_path)
            if attr:
                is_dir = bool(attr['st_mode'] & 0o40000)
                results.append({
                    "name": e,
                    "path": full_path,
                    "type": "directory" if is_dir else "file",
                    "size": attr.get("st_size", 0),
                    "mtime": attr.get("st_mtime", 0)
                })
        return results
