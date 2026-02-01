import ipaddress
import threading
import time
from dataclasses import dataclass

@dataclass
class Lease:
    """IP address lease record."""
    address: str  # Raw address, no CIDR suffix
    holder: str
    expires_at: float

class AddressPool:
    """Manages IP address allocation within a subnet."""
    
    def __init__(self, network: str = "10.0.0.0/24", reserved: int = 2, ttl: int = 3600):
        self._network = ipaddress.ip_network(network)
        self._reserved = reserved
        self._ttl = ttl
        self._leases: dict[str, Lease] = {}  # address -> Lease
        self._holder_map: dict[str, str] = {}  # holder fingerprint -> address
        self._lock = threading.Lock()
    
    def allocate(self, holder: str) -> str:
        """Allocate an IP for a holder, reusing existing lease if present.
        
        Returns:
            CIDR address string (e.g., '10.0.0.2/32').
        """
        with self._lock:
            self._cleanup()
            
            # Check if holder already has a lease
            if holder in self._holder_map:
                addr = self._holder_map[holder]
                self._leases[addr].expires_at = time.time() + self._ttl
                return f"{addr}/32"
            
            # Find next free address
            for i, host in enumerate(self._network.hosts()):
                if i < self._reserved:
                    continue
                
                addr = str(host)
                if addr not in self._leases:
                    # Create new lease
                    self._leases[addr] = Lease(addr, holder, time.time() + self._ttl)
                    self._holder_map[holder] = addr
                    return f"{addr}/32"
            
            raise RuntimeError("Address pool exhausted")
    
    def release(self, holder: str) -> None:
        """Release any lease held by the holder."""
        with self._lock:
            if holder in self._holder_map:
                addr = self._holder_map.pop(holder)
                self._leases.pop(addr, None)
    
    def _cleanup(self):
        """Remove expired leases (internal use only)."""
        now = time.time()
        expired = [a for a, l in self._leases.items() if l.expires_at < now]
        
        for addr in expired:
            lease = self._leases.pop(addr)
            # Remove from holder map
            # Note: A holder might have multiple leases if we allow that policy later,
            # but currently it's 1:1. Safe removal:
            if self._holder_map.get(lease.holder) == addr:
                self._holder_map.pop(lease.holder)
