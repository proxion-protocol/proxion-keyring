import requests

def test_warden():
    url = "http://localhost:8788/warden/simulate"
    
    print("--- Warden Perimeter Test ---")
    
    # Test 1: Known tracker
    resp = requests.post(url, json={"domain": "google-analytics.com"})
    print(f"Checking 'google-analytics.com': {resp.json()['action']}")
    
    # Test 2: Another common tracker
    resp = requests.post(url, json={"domain": "doubleclick.net"})
    print(f"Checking 'doubleclick.net': {resp.json()['action']}")
    
    # Test 3: Clean domain
    resp = requests.post(url, json={"domain": "wikipedia.org"})
    print(f"Checking 'wikipedia.org': {resp.json()['action']}")
    
    # Test 4: Check stats
    resp = requests.get("http://localhost:8788/warden/stats")
    print("\n--- Current Warden Metrics ---")
    print(resp.json())

if __name__ == "__main__":
    try:
        test_warden()
    except Exception as e:
        print(f"Test failed: {e}")
