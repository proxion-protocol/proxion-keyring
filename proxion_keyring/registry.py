import os
import json

class AppRegistry:
    def __init__(self, registry_path=None):
        if registry_path is None:
            # Heuristic to find registry.json in integrations/
            cli_dir = os.path.dirname(os.path.abspath(__file__))
            registry_path = os.path.abspath(os.path.join(cli_dir, "../../integrations/registry.json"))
        
        self.registry_path = registry_path
        self._data = {"apps": {}}
        self._load()

    def _load(self):
        if os.path.exists(self.registry_path):
            with open(self.registry_path, "r") as f:
                self._data = json.load(f)

    def get_subpath(self, app_name):
        """Get the storage subpath on P: for an app."""
        app_data = self._data.get("apps", {}).get(app_name)
        if app_data:
            return app_data.get("path")
        return f"apps/{app_name}" # Default fallback

    def get_app_path(self, app_name):
        """Find the integration folder on the host filesystem."""
        integrations_dir = os.path.dirname(self.registry_path)
        
        # Try exact name first
        p = os.path.join(integrations_dir, app_name)
        if os.path.exists(p): return p
        
        # Try with -integration suffix
        p = os.path.join(integrations_dir, f"{app_name}-integration")
        if os.path.exists(p): return p
        
        return None
