import hashlib
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class MerkleTree:
    """
    A lightweight, pure-Python Merkle Tree implementation for verifiable identity logs.
    Supports proof generation and verification.
    """
    
    def __init__(self, leaves: List[str] = None):
        self.leaves = [self._hash(l) for l in (leaves or [])]
        self.levels = []
        if self.leaves:
            self._build_tree()

    def _hash(self, data: str) -> str:
        if isinstance(data, str):
            data = data.encode('utf-8')
        return hashlib.sha256(data).hexdigest()

    def _build_tree(self):
        self.levels = [self.leaves]
        current_level = self.leaves
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                next_level.append(self._hash(left + right))
            self.levels.append(next_level)
            current_level = next_level

    def get_root(self) -> Optional[str]:
        return self.levels[-1][0] if self.levels else None

    def add_leaf(self, leaf: str):
        self.leaves.append(self._hash(leaf))
        self._build_tree()

    def get_audit_proof(self, index: int) -> List[Dict[str, str]]:
        """Generate a Merkle Proof for a leaf at a given index."""
        proof = []
        if index < 0 or index >= len(self.leaves):
            return proof

        current_index = index
        for level in self.levels[:-1]:
            is_right = current_index % 2 == 1
            sibling_index = current_index - 1 if is_right else current_index + 1
            
            if sibling_index < len(level):
                proof.append({
                    "position": "left" if is_right else "right",
                    "hash": level[sibling_index]
                })
            else:
                # If no sibling (odd leaf count), the leaf is its own sibling
                proof.append({
                    "position": "right",
                    "hash": level[current_index]
                })
            current_index //= 2
            
        return proof

    @staticmethod
    def verify_proof(leaf: str, proof: List[Dict[str, str]], root: str) -> bool:
        """Verify a Merkle Proof against a known root."""
        current_hash = hashlib.sha256(leaf.encode('utf-8')).hexdigest()
        
        for p in proof:
            if p["position"] == "left":
                current_hash = hashlib.sha256((p["hash"] + current_hash).encode('utf-8')).hexdigest()
            else:
                current_hash = hashlib.sha256((current_hash + p["hash"]).encode('utf-8')).hexdigest()
                
        return current_hash == root

class MerkleTransparencyLog:
    """
    Manages a verifiable log of identity events (e.g. key rotations, peer discovery).
    Persists to a Solid Pod as a verifiable sequence.
    """
    
    def __init__(self, stash_manager, log_path: str = "/system/identity_log.json"):
        self.stash = stash_manager
        self.log_path = log_path
        self.tree = MerkleTree()
        self._load_log()

    def _load_log(self):
        try:
            content = self.stash.storage_ls(self.log_path)
            # Future: Full load and rebuild tree from stash
            pass
        except:
            pass

    def append_event(self, event_type: str, data: Dict[str, Any]):
        """Append a signed event to the log and update the Merkle Root."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": hashlib.sha256(str(data).encode()).hexdigest()[:8], # Mock sequence
        }
        event_str = json.dumps(event, sort_keys=True)
        self.tree.add_leaf(event_str)
        
        # In production: write back to Stash (Solid Pod)
        logger.info(f"IdentityLog: Appended {event_type}. New Root: {self.tree.get_root()[:8]}...")
        return {
            "root": self.tree.get_root(),
            "event": event
        }
