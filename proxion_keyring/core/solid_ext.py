import os
import json
from typing import Dict, Any, List
from datetime import datetime

class SolidExtensions:
    """Automated SOLID metadata and structural enhancements for the Proxion Pod."""
    
    TYPE_MAPPINGS = {
        "media/immich": "http://schema.org/ImageObject",
        "media/music": "http://schema.org/AudioObject",
        "media/movies": "http://schema.org/VideoObject",
        "media/tv": "http://schema.org/VideoObject",
        "media/books": "http://schema.org/Book",
        "media/comics": "http://schema.org/Book",
        "office/tasks": "http://schema.org/Checklist",
        "web/bookmarks": "http://schema.org/BookmarkAction",
        "social/mastodon": "http://rdfs.org/sioc/ns#Micropost",
        "knowledge/silverbullet": "http://schema.org/Note",
        "finance/budget": "http://schema.org/FinancialProduct"
    }

    def __init__(self, manager):
        self.manager = manager
        self.pod_root = self.manager.pod_local_root
        self.settings_dir = os.path.join(self.pod_root, "settings")
        os.makedirs(self.settings_dir, exist_ok=True)

    def generate_type_indexes(self):
        """Generate public and private Type Indexes based on registered apps."""
        print("RS: Syncing SOLID Type Indexes...")
        
        apps = self.manager.registry._data.get("apps", {})
        
        # We'll split between public and private based on typical usage
        # This can be made more granular later
        public_entries = []
        private_entries = []
        
        for app_id, app_info in apps.items():
            path = app_info.get("path")
            if not path: continue
            
            # Map path to SOLID Type
            solid_type = self._map_to_type(path)
            if not solid_type: continue
            
            entry = {
                "id": f"#{app_id}",
                "type": solid_type,
                "instance": f"/{path}/"
            }
            
            # Heuristic: social and public web stuff is public, media/finance is private
            if path.startswith(("social", "web")):
                public_entries.append(entry)
            else:
                private_entries.append(entry)
        
        self._write_index(os.path.join(self.settings_dir, "publicTypeIndex.ttl"), public_entries, is_public=True)
        self._write_index(os.path.join(self.settings_dir, "privateTypeIndex.ttl"), private_entries, is_public=False)

    def _map_to_type(self, path: str) -> str:
        # Check direct mapping
        if path in self.TYPE_MAPPINGS:
            return self.TYPE_MAPPINGS[path]
        
        # Check prefix mapping
        for prefix, mapping in self.TYPE_MAPPINGS.items():
            if path.startswith(prefix):
                return mapping
        return None

    def _write_index(self, file_path: str, entries: List[Dict], is_public: bool):
        """Write Type Index in Turtle format."""
        now = datetime.now().isoformat() + "Z"
        
        turtle = [
            "@prefix : <#>.",
            "@prefix solid: <http://www.w3.org/ns/solid/terms#>.",
            "@prefix schema: <http://schema.org/>.",
            "@prefix sioc: <http://rdfs.org/sioc/ns#>.",
            "",
            f"<> a solid:{'Listing' if is_public else 'Unlisted'}Document, solid:TypeIndex;"
        ]
        
        if entries:
            for i, entry in enumerate(entries):
                is_last = (i == len(entries) - 1)
                turtle.append(f"    solid:hasRegistration <{entry['id']}>{';' if not is_last else '.'}")
            
            for entry in entries:
                turtle.append("")
                turtle.append(f"<{entry['id']}> a solid:TypeRegistration;")
                turtle.append(f"    solid:forClass <{entry['type']}>;")
                turtle.append(f"    solid:instance <{entry['instance']}>.")
        else:
            turtle[-1] = turtle[-1].replace(";", ".")

        with open(file_path, "w") as f:
            f.write("\n".join(turtle))
        
        # Ensure .acl is present if not already
        self._ensure_acl(file_path, is_public)

    def generate_metadata(self, pod_path: str):
        """Generate a .meta Turtle sidecar for a resource with technical metadata."""
        local_path = self.manager.stash.pod_proxy.hub._route(pod_path)[0]._safe_path(pod_path)
        if not os.path.exists(local_path) or os.path.isdir(local_path):
            return

        meta_path = local_path + ".meta"
        if os.path.exists(meta_path):
            return # Don't overwrite existing metadata for now

        # 1. Gather Basic Stats
        st = os.stat(local_path)
        mtime = datetime.fromtimestamp(st.st_mtime).isoformat() + "Z"
        size = st.st_size
        basename = os.path.basename(pod_path)

        turtle = [
            "@prefix : <#>.",
            "@prefix terms: <http://purl.org/dc/terms/>.",
            "@prefix stat: <http://www.w3.org/ns/posix/stat#>.",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#>.",
            "",
            f"<{basename}> a terms:File;"
        ]
        turtle.append(f"    terms:modified \"{mtime}\"^^xsd:dateTime;")
        turtle.append(f"    stat:size {size}.")

        # 2. Heuristic: Media Metadata (Inverted RDF)
        if basename.lower().endswith((".mp3", ".flac", ".m4a")):
             turtle[-1] = turtle[-1].replace(".", ";")
             turtle.append("    a <http://schema.org/AudioObject>.")
        elif basename.lower().endswith((".mp4", ".mkv", ".mov")):
             turtle[-1] = turtle[-1].replace(".", ";")
             turtle.append("    a <http://schema.org/VideoObject>.")
        
        with open(meta_path, "w") as f:
            f.write("\n".join(turtle))

    def map_token_to_acl(self, token_payload: Dict, resource_path: str):
        """Map a Proxion Capability Token to a SOLID .acl file."""
        # This is used when we want to 'solidify' a capability for external apps
        local_path = self.manager.stash.pod_proxy.hub._route(resource_path)[0]._safe_path(resource_path)
        acl_path = local_path + ".acl"
        
        holder_webid = f"https://{token_payload['holder_key_fingerprint']}.solid.community/profile/card#me"
        permissions = token_payload.get("permissions", [])
        
        modes = []
        for p in permissions:
            perm_type = p[0] if isinstance(p, list) else p
            if perm_type == "READ": modes.append("acl:Read")
            if perm_type in ["WRITE", "CREATE"]: modes.append("acl:Write")
            if perm_type == "DELETE": modes.append("acl:Write") # WAC uses Write for delete
            
        if not modes: return

        acl = [
            "@prefix acl: <http://www.w3.org/ns/auth/acl#>.",
            "",
            f"<#token-bound-access>"
        ]
        acl.append(f"    a acl:Authorization;")
        acl.append(f"    acl:agent <{holder_webid}>;")
        acl.append(f"    acl:accessTo <{os.path.basename(resource_path)}>;")
        acl.append(f"    acl:mode {', '.join(set(modes))}.")
        
        with open(acl_path, "w") as f:
            f.write("\n".join(acl))

    def _ensure_acl(self, file_path: str, is_public: bool):
        acl_path = file_path + ".acl"
        if os.path.exists(acl_path): return
        
        webid = f"https://{self.manager.identity.get_public_key_hex()}.solid.community/profile/card#me"
        
        acl = [
            "@prefix acl: <http://www.w3.org/ns/auth/acl#>.",
            "@prefix foaf: <http://xmlns.com/foaf/0.1/>.",
            "",
            "<#owner>"
        ]
        
        acl.append(f"    a acl:Authorization;")
        acl.append(f"    acl:agent <{webid}>;")
        acl.append(f"    acl:accessTo <{os.path.basename(file_path)}>;")
        acl.append(f"    acl:mode acl:Read, acl:Write, acl:Control.")
        
        if is_public:
            acl.append("")
            acl.append("<#public>")
            acl.append("    a acl:Authorization;")
            acl.append("    acl:agentClass foaf:Agent;")
            acl.append(f"    acl:accessTo <{os.path.basename(file_path)}>;")
            acl.append("    acl:mode acl:Read.")
            
        with open(acl_path, "w") as f:
            f.write("\n".join(acl))
