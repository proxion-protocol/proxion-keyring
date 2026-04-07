import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from proxion_keyring.core.psi import RSAPSI

def test_psi_flow():
    print("--- Testing RSA-PSI Flow ---")
    
    # 1. Setup Server and Client sets
    server_set = ["alice@proxion.me", "bob@proxion.me", "charlie@node.io"]
    client_set = ["bob@proxion.me", "eve@hacker.io", "charlie@node.io"]
    
    print(f"Server Set: {server_set}")
    print(f"Client Set: {client_set}")

    # 2. Server encrypts its own set
    server = RSAPSI()
    server_signed = server.server_encrypt_set(server_set)
    print("Server signed its own set.")

    # 3. Client blinds its set
    client = RSAPSI()
    client.public_key = server.public_key # Client gets server's pubkey
    blinded_data = client.client_blind_elements(client_set)
    blinded_values = [b[0] for b in blinded_data]
    r_values = [b[1] for b in blinded_data]
    print("Client blinded its set.")

    # 4. Server signs client's blinded set
    server_signed_blinded = server.server_sign_blinded(blinded_values)
    print("Server signed client's blinded set.")

    # 5. Client unblinds
    client_unblinded = client.client_unblind_elements(server_signed_blinded, r_values)
    print("Client unblinded the results.")

    # 6. Intersection check
    intersection = []
    for i, val in enumerate(client_unblinded):
        if val in server_signed:
            intersection.append(client_set[i])
            
    print(f"Discovered Intersection: {intersection}")
    
    expected = ["bob@proxion.me", "charlie@node.io"]
    if set(intersection) == set(expected):
        print("[+] PSI logic verified successfully!")
    else:
        print(f"[!] PSI logic mismatch. Expected {expected}")

if __name__ == "__main__":
    test_psi_flow()
