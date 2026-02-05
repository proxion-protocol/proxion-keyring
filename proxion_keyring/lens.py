import os
import json
import threading
import time
from typing import List, Dict, Any
from datetime import datetime

class Lens:
    """
    Global Indexed Search for the Proxion Suite.
    Scans mounted FUSE drives and indexes filenames and basic metadata.
    """
    
    # Standard Mount Points defined in the Vision
    MOUNT_POINTS = {
        "Z:": "Photos (Immich)",
        "Y:": "Notes (Joplin)",
        "X:": "Media (Jellyfin)",
        "W:": "Smart Home (HA)",
        "V:": "Finance (Firefly)",
        "U:": "Read Later (Wallabag)",
        "S:": "Office (CryptPad)",
        "T:": "Passwords (KeePassXC)",
        "Q:": "VSCode Sync"
    }

    def __init__(self, manager=None, data_dir: str = None):
        self.manager = manager
        if data_dir is None:
            data_dir = os.path.join(os.path.expanduser("~"), ".proxion")
        
        self.data_dir = data_dir
        self.index_path = os.path.join(data_dir, "lens_index.json")
        self.index: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self.is_scanning = False
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self._load_index()

    def _load_index(self):
        with self._lock:
            if os.path.exists(self.index_path):
                try:
                    with open(self.index_path, 'r') as f:
                        self.index = json.load(f)
                except:
                    self.index = []

    def _save_index(self):
        with self._lock:
            with open(self.index_path, 'w') as f:
                json.dump(self.index, f, indent=2)

    def refresh_index(self):
        """Wrapper for Manager compatibility."""
        threading.Thread(target=self.scan_mounts, daemon=True).start()

    def start_background_scan(self, interval_seconds: int = 3600):
        """Periodically scan mounts in a background thread."""
        def scan_loop():
            while not self._stop_event.is_set():
                self.scan_mounts()
                # Wait for interval or stop event
                self._stop_event.wait(interval_seconds)
                
        thread = threading.Thread(target=scan_loop, daemon=True)
        thread.start()

    def stop(self):
        self._stop_event.set()

    def scan_mounts(self):
        """Walk through all active Proxion mount points and index files."""
        if self.is_scanning:
            return
        
        print("[Lens] Starting global scan...")
        self.is_scanning = True
        new_index = []
        
        # 1. Physical Mount Points (Legacy)
        for drive, label in self.MOUNT_POINTS.items():
            if os.path.exists(drive):
                print(f"[Lens] Indexing {label} ({drive})...")
                try:
                    for root, dirs, files in os.walk(drive):
                        for name in files:
                            full_path = os.path.join(root, name)
                            try:
                                stat = os.stat(full_path)
                                new_index.append({
                                    "name": name,
                                    "path": full_path,
                                    "drive": drive,
                                    "label": label,
                                    "size": stat.st_size,
                                    "mtime": stat.st_mtime,
                                    "type": os.path.splitext(name)[1].lower(),
                                    "proxion_status": "local"
                                })
                            except: continue
                except Exception as e:
                    print(f"[Lens] Failed to scan {drive}: {e}")

        # 2. Virtual Pod Space (Solid Stash)
        if self.manager and hasattr(self.manager, 'pod_proxy') and self.manager.pod_proxy:
            print("[Lens] Indexing Solid Pod Space...")
            self._scan_pod_recursive(self.manager.pod_proxy.hub, "/", new_index)

        with self._lock:
            self.index = new_index
            self._save_index()
            
        self.is_scanning = False
        print(f"[Lens] Scan complete. Indexed {len(self.index)} items.")

    def _scan_pod_recursive(self, hub, path, results):
        """Recursively walk the HybridHub."""
        try:
            entries = hub.list_dir(path)
            for e in entries:
                if e in [".", ".."]: continue
                full_p = os.path.join(path, e).replace("\\", "/")
                attr = hub.get_attr(full_p)
                if not attr: continue
                
                is_dir = bool(attr['st_mode'] & 0o40000)
                if is_dir:
                    self._scan_pod_recursive(hub, full_p, results)
                else:
                    results.append({
                        "name": e,
                        "path": f"/pod{full_p}",
                        "drive": "POD:",
                        "label": "Solid Stash",
                        "size": attr.get('st_size', 0),
                        "mtime": attr.get('st_mtime', 0),
                        "type": os.path.splitext(e)[1].lower(),
                        "proxion_status": attr.get("proxion_status", "unknown")
                    })
        except:
            pass

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search the index for matching filenames."""
        query = query.lower()
        results = []
        
        with self._lock:
            for item in self.index:
                if query in item["name"].lower():
                    results.append(item)
                    
        # Return top 50 results
        return results[:50]

    def get_status(self) -> Dict[str, Any]:
        """Return indexer status and statistics."""
        with self._lock:
            return {
                "item_count": len(self.index),
                "is_scanning": self.is_scanning,
                "last_index_path": self.index_path,
                "active_mounts": [d for d in self.MOUNT_POINTS.keys() if os.path.exists(d)]
            }
