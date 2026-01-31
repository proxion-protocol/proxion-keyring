import json
import os
from datetime import datetime, timezone
import threading

class FileStore:
    """Simple JSON-backed store for ephemeral CP state (Tickets)."""
    
    def __init__(self, filename: str):
        self.filename = filename
        self._lock = threading.Lock()
        self._data: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self._data = json.load(f)
                    # Convert some string dates back to datetime if needed, 
                    # but for tickets we usually just check TTL.
            except Exception as e:
                print(f"Store load failed: {e}")
                self._data = {}

    def _save(self):
        try:
            with open(self.filename, 'w') as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"Store save failed: {e}")

    def set(self, key: str, value: dict):
        with self._lock:
            self._data[key] = value
            self._save()

    def get(self, key: str) -> dict | None:
        with self._lock:
            self._load()
            return self._data.get(key)

    def delete(self, key: str):
        with self._lock:
            self._load()
            if key in self._data:
                del self._data[key]
                self._save()

    def list_keys(self) -> list[str]:
        with self._lock:
            self._load()
            return list(self._data.keys())

    def purge_expired(self, ttl_seconds: int):
        """Purge items older than ttl_seconds."""
        now = datetime.now(timezone.utc).timestamp()
        to_delete = []
        with self._lock:
            self._load()
            for key, val in self._data.items():
                created_at = val.get("created_at_ts")
                if created_at and (now - created_at) > ttl_seconds:
                    to_delete.append(key)
            
            for key in to_delete:
                del self._data[key]
            
            if to_delete:
                self._save()
        return len(to_delete)
