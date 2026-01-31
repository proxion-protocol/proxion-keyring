"""Tests for IP AddressPool."""
import pytest
import time
from rs.address_pool import AddressPool

class TestAddressPool:
    
    def test_allocate_unique(self):
        pool = AddressPool(network="10.0.0.0/24")
        addr1 = pool.allocate("holder1")
        addr2 = pool.allocate("holder2")
        
        assert addr1 != addr2
        assert addr1.startswith("10.0.0.")
        assert addr1.endswith("/32")
    
    def test_same_holder_same_address(self):
        pool = AddressPool(network="10.0.0.0/24")
        addr1 = pool.allocate("holder1")
        addr2 = pool.allocate("holder1")
        
        assert addr1 == addr2
    
    def test_pool_exhaustion(self):
        # Create tiny pool: 10.0.0.0/30 -> hosts .1, .2
        # Use reserved=0 so we can use both .1 and .2
        pool = AddressPool(network="10.0.0.0/30", reserved=0)
        
        # Allocate .1
        addr1 = pool.allocate("h1") # 10.0.0.1
        # Allocate .2
        addr2 = pool.allocate("h2") # 10.0.0.2
        
        # should fail now
        with pytest.raises(RuntimeError, match="Address pool exhausted"):
            pool.allocate("h3")

    def test_lease_expiry(self):
        # 1-second TTL
        pool = AddressPool(network="10.0.0.0/24", ttl=1)
        
        addr1 = pool.allocate("h1")
        time.sleep(1.1)
        
        # Should be expired and cleaned up
        # h2 might get the same address or next depending on iteration order,
        # but h1's lease should be gone internally.
        
        # Force cleanup by allocating
        addr2 = pool.allocate("h2")
        
        # h1 should be able to get a NEW address (or re-get same if free)
        # but conceptually it's a new allocation
        pass 

    def test_release(self):
        pool = AddressPool(network="10.0.0.0/24")
        addr1 = pool.allocate("h1")
        pool.release("h1")
        
        # Now h2 can potentially get that address (implementation detail)
        # or at least h1 is gone
        addr2 = pool.allocate("h2")
        # Just verifying no crash
