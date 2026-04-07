import os
import platform
import logging
import threading
import time

logger = logging.getLogger(__name__)

class CaffeineManager:
    """
    Prevents the host system from entering sleep/hibernate mode during active mesh sessions.
    Supports Windows (SetThreadExecutionState) and Linux (systemd-inhibit placeholder).
    """
    
    # Windows Constants
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_AWAYMODE_REQUIRED = 0x00000040

    def __init__(self):
        self.active = False
        self._thread = None
        self.os_type = platform.system().lower()

    def _stay_awake_windows(self):
        """Invoke Windows API to prevent sleep."""
        import ctypes
        logger.info("Caffeine: Engaging Windows Stay-Awake loop.")
        while self.active:
            # ES_SYSTEM_REQUIRED | ES_CONTINUOUS
            ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED)
            time.sleep(30)
        
        # Reset state on exit
        ctypes.windll.kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
        logger.info("Caffeine: Windows Stay-Awake loop terminated.")

    def _stay_awake_linux(self):
        """Engage Linux systemd-inhibit or similar."""
        logger.info("Caffeine: Engaging Linux Stay-Awake (Placeholders).")
        # In a real implementation, we would use dbus to talk to systemd-logind
        # or execute 'systemd-inhibit --what=sleep ...'
        while self.active:
            time.sleep(30)
        logger.info("Caffeine: Linux Stay-Awake loop terminated.")

    def start(self):
        """Start the caffeine loop."""
        if self.active:
            return
            
        self.active = True
        if self.os_type == 'windows':
            self._thread = threading.Thread(target=self._stay_awake_windows, daemon=True)
        else:
            self._thread = threading.Thread(target=self._stay_awake_linux, daemon=True)
            
        self._thread.start()
        logger.info("Caffeine: Mode Engage.")

    def stop(self):
        """Stop the caffeine loop."""
        self.active = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Caffeine: Mode Disengaged.")
