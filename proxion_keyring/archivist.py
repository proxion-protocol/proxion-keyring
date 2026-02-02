import os
import requests
import datetime
from typing import Dict, Any

class Archivist:
    """The Memory Keeper: Captures and saves web snapshots to the Pod."""
    
    def __init__(self, manager):
        self.manager = manager
        self.snapshots_dir = "snapshots"
        if not os.path.exists(self.snapshots_dir):
            os.makedirs(self.snapshots_dir)

    def capture_snapshot(self, url: str) -> Dict[str, Any]:
        """Fetch URL content and save as a snapshot."""
        print(f"Archivist: Capturing snapshot of {url}...")
        
        # Clean URL
        if not url.startswith("http"):
            url = "https://" + url
            
        try:
            # We use a custom User-Agent to avoid being blocked, but stay identifiable
            headers = {
                "User-Agent": "ProxionArchivist/1.0 (Proxion Snapshot Engine; +https://proxion.suite)"
            }
            resp = requests.get(url, timeout=15, headers=headers)
            
            if resp.status_code != 200:
                return {"error": f"Failed to fetch: HTTP {resp.status_code}"}
            
            # Generate Metadata
            domain = url.split("//")[-1].split("/")[0]
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{domain.replace('.', '_')}.html"
            filepath = os.path.join(self.snapshots_dir, filename)
            
            # Save to 'Stash' (Local snapshots dir for now)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(resp.text)
            
            # 3. Register with Lens immediately so it's searchable
            if hasattr(self.manager, 'lens'):
                self.manager.lens.index.append({
                    "name": f"Snapshot: {domain} ({timestamp})",
                    "path": f"/stash/archive/{filename}",
                    "type": "document"
                })
            
            return {
                "status": "Archived",
                "filename": filename,
                "url": url,
                "size": len(resp.text),
                "timestamp": timestamp
            }
            
        except Exception as e:
            print(f"Archivist: Capture failed: {e}")
            return {"error": str(e)}

    def get_snapshots(self) -> list:
        """List all captured snapshots."""
        if not os.path.exists(self.snapshots_dir):
            return []
        return os.listdir(self.snapshots_dir)
