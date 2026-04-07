import sys
import os
from pprint import pprint

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from proxion_keyring.core.telemetry import TelemetryManager
    
    print("--- Initializing TelemetryManager ---")
    tm = TelemetryManager()
    
    print("--- Fetching System Pulse ---")
    pulse = tm.get_pulse()
    
    pprint(pulse)
    
    if pulse.get("glances", {}).get("status") == "offline":
        print("\n[!] Glances appears to be offline. Make sure Glances is running with 'glances -w' or similar.")
    else:
        print("\n[+] Telemetry collection successful!")

except ImportError as e:
    print(f"[!] Import error: {e}")
except Exception as e:
    print(f"[!] Error: {e}")
