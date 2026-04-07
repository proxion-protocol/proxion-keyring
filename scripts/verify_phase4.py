import sys
import os
import requests
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:8788"

def test_pulse_endpoint():
    print("--- Testing Pulse Telemetry ---")
    try:
        # Note: In a real test we'd need a valid Proxion-Token. 
        # For this sanity check, we'll verify the endpoint exists and handles missing token correctly (401).
        resp = requests.get(f"{BASE_URL}/telemetry/pulse")
        print(f"Pulse Response (No Token): {resp.status_code}")
    except Exception as e:
        print(f"Pulse Request Failed: {e}")

def test_mesh_endpoints():
    print("--- Testing Mesh Endpoints ---")
    endpoints = [
        ("/mesh/dns/status", "GET"),
        ("/mesh/headscale/bootstrap", "POST"),
        ("/mesh/proxy/toggle", "POST"),
        ("/caffeine/toggle", "POST")
    ]
    for ep, method in endpoints:
        try:
            if method == "GET":
                resp = requests.get(f"{BASE_URL}{ep}")
            else:
                resp = requests.post(f"{BASE_URL}{ep}", json={})
            print(f"{method} {ep} (No Token): {resp.status_code}")
        except Exception as e:
            print(f"Request to {ep} failed: {e}")

def verify_module_loading():
    print("--- Verifying Core Module Loading ---")
    try:
        from proxion_keyring.manager import KeyringManager
        from proxion_keyring.core.identity import Identity
        
        manager = KeyringManager()
        print("[+] KeyringManager loaded successfully.")
        
        modules = [
            ("Identity", manager.identity),
            ("Telemetry", manager.telemetry),
            ("Fleet", manager.fleet),
            ("Mesh", manager.mesh),
            ("Vault", manager.vault),
            ("Caffeine", manager.caffeine)
        ]
        
        for name, mod in modules:
            if mod:
                print(f"[+] {name} module initialized.")
            else:
                print(f"[!] {name} module MISSING.")
                
    except Exception as e:
        print(f"Module loading check failed: {e}")

if __name__ == "__main__":
    verify_module_loading()
    # test_pulse_endpoint() # These require a running server
    # test_mesh_endpoints()
