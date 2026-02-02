
import requests
import os

def test_proxy():
    # Construct a path that matches what mount.py would send
    # c:\Users\hobo\Desktop\Proxion\proxion-core\storage\test_proxy_dir
    base = "c:/Users/hobo/Desktop/Proxion/proxion-core/storage"
    target = f"{base}/test_proxy_dir"
    url = f"http://localhost:8089/pod/{target}/"
    
    print(f"Testing direct PUT to {url}")
    
    headers = {
        "Content-Type": "text/turtle",
        "Link": "<http://www.w3.org/ns/ldp#BasicContainer>; rel=\"type\""
    }
    
    try:
        resp = requests.put(url, headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_proxy()
