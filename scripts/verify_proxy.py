import requests
import time
import subprocess
import os

def test_proxy():
    print("Launching Resource Server with Pod Proxy...")
    # Run server in background
    cmd = ["python", "-m", "proxion_keyring.rs.server"]
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    proc = subprocess.Popen(cmd, env=env)
    
    time.sleep(3) # Wait for startup
    
    try:
        # Test 1: Ping the Proxy
        # (It should try to fetch from the mock pod URL)
        print("Testing Proxy (8089)...")
        try:
            # We use a path that doesn't trigger tunnel routing first
            response = requests.get("http://127.0.0.1:8089/pod/hello.txt", timeout=5)
            print(f"Proxy Response: {response.status_code}")
            # Note: This might fail 502 because the mock Pod doesn't exist, 
            # but getting a response from the proxy is the goal.
        except Exception as e:
            print(f"Proxy connection failed: {e}")

        # Test 2: Verify RS is still up (8788)
        print("Testing RS (8788)...")
        rs_resp = requests.get("http://127.0.0.1:8788/sessions", timeout=2)
        print(f"RS Response: {rs_resp.status_code} {rs_resp.json()}")

    finally:
        proc.terminate()
        print("Test complete. Process killed.")

if __name__ == "__main__":
    test_proxy()
