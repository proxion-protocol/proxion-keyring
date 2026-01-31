import platform
from .base import WireGuardBackend
from .mock import MockBackend

def create_backend(use_mock: bool = False) -> WireGuardBackend:
    """Create backend. Only Linux supports mutation in Phase 1."""
    if use_mock:
        return MockBackend()
    
    system = platform.system().lower()
    if system == "linux":
        from .linux import LinuxBackend
        return LinuxBackend()
    elif system == "windows":
        from .windows import WindowsBackend
        return WindowsBackend()
    
    # macOS/Windows: mutation not supported in Phase 1
    # Users should use config-generation mode on these platforms.
    raise RuntimeError(
        f"WireGuard mutation not supported on {system} in Phase 1. "
        "Set KLEITIKON_WG_MUTATION=false for config-generation mode."
    )
