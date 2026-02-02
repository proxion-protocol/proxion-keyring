import json
import os
import uuid
import threading
from typing import List, Dict, Any
from datetime import datetime, timezone
from cryptography.hazmat.primitives import serialization
from .identity import derive_child_key

class MeshCoordinator:
    """
    Manages Mesh Groups (Private LANs).
    Orchestrates full-mesh connectivity by checking relationships.
    """
    
    def __init__(self, key_manager):
        self.manager = key_manager
        self._lock = threading.Lock()
        self.groups: Dict[str, Dict] = {} # group_id -> {name, members: [pubkeys]}
        self._load_groups()

    def _load_groups(self):
        if os.path.exists("mesh_groups.json"):
            try:
                with open("mesh_groups.json", "r") as f:
                    self.groups = json.load(f)
            except:
                self.groups = {}

    def _save_groups(self):
        try:
            with open("mesh_groups.json", "w") as f:
                json.dump(self.groups, f, indent=2)
        except Exception as e:
            print(f"Failed to save mesh groups: {e}")

    def create_group(self, name: str) -> str:
        """Create a new Mesh Group and join it with a derived identity."""
        group_id = str(uuid.uuid4())
        
        # Unlinkability: Derive a specific identity for this group
        # This way, our presence in this group cannot be correlated 
        # with our presence in other groups by an observer.
        my_derived_key = derive_child_key(self.manager.private_key, group_id)
        my_pub_hex = my_derived_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        ).hex()

        with self._lock:
            self.groups[group_id] = {
                "name": name,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "members": [my_pub_hex],
                "my_derived_pubkey": my_pub_hex
            }
            self._save_groups()
            
        print(f"Mesh: Created group '{name}' with Unlinkable Identity {my_pub_hex[:8]}")
        return group_id

    def list_groups(self) -> Dict[str, Any]:
        with self._lock:
             return self.groups

    def add_member(self, group_id: str, peer_pubkey: str):
        """
        Add a peer to a group.
        Triggers Auto-Mesh: Ensure this peer has relationships with all other members.
        """
        with self._lock:
            if group_id not in self.groups:
                raise ValueError("Group not found")
            
            group = self.groups[group_id]
            if peer_pubkey in group["members"]:
                return # Already member
            
            # 1. Add to list
            group["members"].append(peer_pubkey)
            self._save_groups()
            
            # 2. Auto-Mesh Logic (Simplified for MVP)
            # In a real mesh, we would broadcast "New Peer" to all existing members.
            # Here, as the Coordinator, we are just tracking the list.
            # The actual "Meshing" implies sending keys.
            # MVP: We just record the intent. The actual WireGuard config generation
            # would iterate this list and add peers.
            
            print(f"Mesh: Added {peer_pubkey[:8]} to group '{group['name']}'. Propagating...")
            
    def remove_member(self, group_id: str, peer_pubkey: str):
        with self._lock:
            if group_id in self.groups:
                if peer_pubkey in self.groups[group_id]["members"]:
                    self.groups[group_id]["members"].remove(peer_pubkey)
                    self._save_groups()
