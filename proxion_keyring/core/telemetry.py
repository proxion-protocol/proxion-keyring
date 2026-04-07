import abc
import logging
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)

class BaseCollector(abc.ABC):
    """Base class for all telemetry providers."""
    
    @abc.abstractmethod
    def collect(self) -> Dict[str, Any]:
        """Fetch real-time metrics from the provider."""
        pass

class GlancesProvider(BaseCollector):
    """Telemetry provider using the Glances API."""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 61208):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}/api/3"

    def collect(self) -> Dict[str, Any]:
        metrics = {}
        try:
            # Fetch essential system metrics
            # Note: We use a short timeout to keep the dashboard responsive
            endpoints = ["cpu", "mem", "sensors", "load", "diskio", "fs"]
            for endpoint in endpoints:
                try:
                    resp = requests.get(f"{self.base_url}/{endpoint}", timeout=1.5)
                    if resp.status_code == 200:
                        metrics[endpoint] = resp.json()
                except requests.exceptions.RequestException:
                    metrics[endpoint] = None
                    
            return {
                "status": "online" if metrics.get("cpu") else "offline",
                "data": metrics,
                "provider": "glances"
            }
        except Exception as e:
            logger.error(f"Failed to collect Glances metrics: {e}")
            return {"status": "error", "error": str(e)}

class TelemetryManager:
    """Manages multiple telemetry collectors and aggregates their data."""
    
    def __init__(self):
        self.collectors: Dict[str, BaseCollector] = {
            "glances": GlancesProvider()
        }

    def get_pulse(self) -> Dict[str, Any]:
        """Aggregate current pulse from all active collectors."""
        pulse = {}
        for name, collector in self.collectors.items():
            pulse[name] = collector.collect()
        return pulse
