import requests
import json

def test_archivist():
    base_url = "http://localhost:8788/archivist/capture"
    
    print("--- Archivist Web Capture Test ---")
    
    # Test 1: Real capture
    target = "http://example.com"
    print(f"Snapping: {target}...")
    try:
        resp = requests.post(base_url, json={"url": target}, timeout=20)
        result = resp.json()
        print(f"Status: {result.get('status', 'ERROR')}")
        if "filename" in result:
            print(f"Success! Saved to {result['filename']} ({result['size']} bytes)")
            
            # Verify indexing
            print("\nVerifying Lens Indexing...")
            lens_url = "http://localhost:8788/lens/search"
            s_resp = requests.get(lens_url, params={"q": "Snapshot"})
            results = s_resp.json()
            found = any(result['filename'] in r['path'] for r in results)
            print(f"Lens found snapshot: {'YES' if found else 'NO'}")
            
    except Exception as e:
        print(f"Capture failed: {e}")

if __name__ == "__main__":
    test_archivist()
