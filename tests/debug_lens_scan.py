import os
import sys

# Setup PYTHONPATH
REPO_ROOT = os.path.dirname(os.path.abspath(os.getcwd()))
sys.path.append(os.path.join(REPO_ROOT, "proxion-keyring"))

from proxion_keyring.lens import Lens

class MockAttr:
    def __init__(self, is_dir=False):
        self.st_mode = 0o40755 if is_dir else 0o100644

class MockHub:
    def list_dir(self, path):
        if path == "/": return ["stash", "cloud"]
        if path == "/stash": return ["local.txt"]
        if path == "/cloud": return ["remote.txt"]
        return []
    
    def get_attr(self, path):
        if path in ["/", "/stash", "/cloud"]: 
            return {"st_mode": 0o40755}
        return {"st_mode": 0o100644, "proxion_status": "mock"}

def test_debug():
    lens = Lens(data_dir=".")
    hub = MockHub()
    results = []
    print("Starting recursive scan...")
    lens._scan_pod_recursive(hub, "/", results)
    print(f"Results: {results}")
    assert len(results) == 2
    assert any("local.txt" in r["name"] for r in results)
    assert any("remote.txt" in r["name"] for r in results)
    print("SUCCESS: Lens scan logic is correct.")

if __name__ == "__main__":
    test_debug()
