from typing import Any, List, Set, Tuple
from dataclasses import dataclass

@dataclass(frozen=True)
class PolicyResult:
    allowed: bool
    permissions: List[Tuple[str, str]]
    reason: str | None = None

class PolicyEngine:
    """Evaluates proxion-keyring policies (JSON-LD)."""

    def evaluate(self, policies: List[dict], ctx_action: str, aud: str, rp_pubkey: str) -> PolicyResult:
        """
        Evaluate a list of policies against a request.
        
        policies: List of policy objects (JSON-LD)
        ctx_action: e.g. "bootstrap"
        aud: Audience (e.g. "wg0")
        rp_pubkey: The public key of the requesting device.
        """
        allowed_actions = set()
        matched = False

        for p in policies:
            # Basic validation of policy structure
            # In a full JSON-LD environment, we'd use expansion/compaction
            # For now, we assume fixed keys as defined in our context.jsonld
            
            applies_to = p.get("applies_to", {})
            if not self._applies_to_device(applies_to, rp_pubkey):
                print(f"PolicyEngine: Policy does NOT apply to device {rp_pubkey}")
                continue

            permits = p.get("permits", [])
            for perm in permits:
                action = perm.get("action")
                resource = perm.get("resource")

                # Normalize behavior for demo compatibility
                norm_action = action
                if action == "bootstrap":
                    norm_action = "channel.bootstrap"
                
                norm_ctx_action = ctx_action
                if ctx_action == "bootstrap":
                    norm_ctx_action = "channel.bootstrap"

                if norm_action == norm_ctx_action and self._resource_matches(resource, aud):
                    matched = True
                    # Always emit the fully qualified action in the token
                    allowed_actions.add(("channel.bootstrap", aud))

        if matched:
            return PolicyResult(True, list(allowed_actions))
        
        return PolicyResult(False, [], "No matching policy found")

    def _applies_to_device(self, applies_to: dict, device_id: str) -> bool:
        if applies_to.get("all_devices") == True:
            return True
        return applies_to.get("device_id") == device_id

    def _resource_matches(self, resource_pattern: str, aud: str) -> bool:
        if resource_pattern == "*":
            return True
        # Simple exact match or prefixed match
        if resource_pattern == aud or resource_pattern == f"rs:{aud}":
            return True
        return False
