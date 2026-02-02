import os
import threading
from typing import Set, Dict

class Warden:
    """The Perimeter Guard: AD-blocking and Tracker filtering."""
    
    def __init__(self, blocklist_url="https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts"):
        self.blocklist_url = blocklist_url
        self.blocked_domains: Set[str] = set()
        self.stats: Dict[str, int] = {"blocked_count": 0}
        self._lock = threading.Lock()
        
        # Load initially
        self.load_blocklist()

    def load_blocklist(self):
        """Fetch and parse the blocklist from a known source."""
        cache_path = "warden_blocklist.txt"
        
        # Check if we have a cached version (production would use a timer to refresh)
        if not os.path.exists(cache_path):
            print("Warden: Downloading perimeter blocklist...")
            try:
                import requests
                resp = requests.get(self.blocklist_url, timeout=10)
                if resp.status_code == 200:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        f.write(resp.text)
            except Exception as e:
                print(f"Warden: Could not download blocklist: {e}")
                # Fallback to a tiny empty set or hardcoded basics
                self.blocked_domains = {"telemetry.microsoft.com", "google-analytics.com"}
                return

        if os.path.exists(cache_path):
            count = 0
            with open(cache_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Standard host file format: 0.0.0.0 domain.com
                    if line.startswith("0.0.0.0 "):
                        parts = line.split()
                        if len(parts) >= 2:
                            self.blocked_domains.add(parts[1])
                            count += 1
            print(f"Warden: Fortress perimeter secured with {count} blocked domains.")

    def should_block(self, domain: str) -> bool:
        """Check if a request should be dropped."""
        # Normalize domain
        domain = domain.lower().strip()
        
        if domain in self.blocked_domains:
            with self._lock:
                self.stats["blocked_count"] += 1
            return True
        return False

    def get_stats(self) -> Dict:
        """Expose metrics for the Mobile PWA."""
        with self._lock:
            return {
                "blocked_total": self.stats["blocked_count"],
                "active_protections": len(self.blocked_domains),
                "status": "active"
            }
