import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proxion_keyring.core.merkle import MerkleTree

def test_merkle_logic():
    print("--- Testing MerkleTree Logic ---")
    leaves = ["eventA", "eventB", "eventC", "eventD"]
    mt = MerkleTree(leaves)
    root = mt.get_root()
    print(f"Root (4 leaves): {root}")

    # Test audit proof for eventC (index 2)
    proof = mt.get_audit_proof(2)
    print(f"Proof for 'eventC': {proof}")

    # Verify proof
    is_valid = MerkleTree.verify_proof("eventC", proof, root)
    print(f"Verification result: {'SUCCESS' if is_valid else 'FAILED'}")

    # Test with odd number of leaves
    mt.add_leaf("eventE")
    root_5 = mt.get_root()
    print(f"Root (5 leaves): {root_5}")
    proof_5 = mt.get_audit_proof(4) # eventE
    is_valid_5 = MerkleTree.verify_proof("eventE", proof_5, root_5)
    print(f"Verification (odd leaves): {'SUCCESS' if is_valid_5 else 'FAILED'}")

if __name__ == "__main__":
    test_merkle_logic()
