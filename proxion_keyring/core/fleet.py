import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class FleetManager:
    """
    Coordinates bulk maintenance operations for the Proxion fleet.
    Integrates with KeyringManager to stop containers and unmount storage safely.
    """
    
    def __init__(self, keyring_manager):
        self.keyring = keyring_manager

    def maintenance_shutdown(self) -> Dict[str, Any]:
        """
        Executes a 'Secure Shutdown' sequence:
        1. Logs the maintenance event.
        2. Stops all integration containers (Orchestrate Down).
        3. Attempts to unmount Proxion FUSE volumes.
        """
        self.keyring.log_event("SHUTDOWN: Initiating maintenance sequence", "Fleet", "Manager", "warning")
        
        # 1. Stop the suite
        suite_results = self.keyring.orchestrate_suite("down", "all")
        
        # 2. Unmount stash if adapter supports it
        unmount_results = self._unmount_storage()
        
        return {
            "containers": suite_results,
            "storage": unmount_results,
            "status": "MAINTENANCE_READY"
        }

    def _unmount_storage(self) -> Dict[str, Any]:
        """Trigger unmount for proxion-fuse volumes."""
        try:
            # We check the adapter for unmount capabilities
            # Adapter logic usually handles OS-specific unmount commands
            if hasattr(self.keyring.adapter, 'unmount_all'):
                self.keyring.adapter.unmount_all()
                return {"status": "SUCCESS", "message": "All storage volumes unmounted"}
            return {"status": "SKIPPED", "message": "Adapter does not support bulk unmount"}
        except Exception as e:
            logger.error(f"Unmount failure: {e}")
            return {"status": "ERROR", "error": str(e)}
