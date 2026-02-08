import os
import json
import threading
from datetime import datetime, timezone
from collections import deque

class EventBus:
    """Unified event bus for cross-process security auditing."""
    
    def __init__(self, log_path: str, max_memory: int = 100):
        self.log_path = log_path
        self.memory_queue = deque(maxlen=max_memory)
        self._lock = threading.Lock()
        
        # Ensure log directory exists
        log_dir = os.path.dirname(self.log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        # Ensure log file exists
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w") as f:
                pass

    def log(self, action: str, resource: str, subject: str = "System", type: str = "info"):
        """Log an event to memory and the shared persistent log."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "resource": resource,
            "subject": subject,
            "type": type  # info, success, warning, error
        }
        
        with self._lock:
            self.memory_queue.append(event)
            
        # Write to shared log for Real-Time Dashboard Stream
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"Guardian: Failed to write to event log: {e}")
            
        print(f"Guardian: {type.upper()} | {action} on {resource} by {subject}")

    def get_recent(self, count: int = 50):
        """Get recent events from memory."""
        with self._lock:
            return list(self.memory_queue)[-count:]
