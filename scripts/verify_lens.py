import requests

def test_lens():
    base_url = "http://localhost:8788/lens/search"
    
    print("--- Lens Unified Search Test ---")
    
    # Test 1: Active search
    resp = requests.get(base_url, params={"q": "Tax"})
    results = resp.json()
    print(f"Query 'Tax' found: {len(results)} items")
    for r in results:
        print(f" - {r['name']} at {r['path']}")
    
    # Test 2: Categorical search
    resp = requests.get(base_url, params={"q": "photo"})
    results = resp.json()
    print(f"Query 'photo' found: {len(results)} items")
    
    # Test 3: Empty results
    resp = requests.get(base_url, params={"q": "nonexistent"})
    print(f"Query 'nonexistent' found: {len(resp.json())} items")

if __name__ == "__main__":
    try:
        test_lens()
    except Exception as e:
        print(f"Test failed: {e}")
