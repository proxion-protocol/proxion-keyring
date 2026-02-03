import os
import json
import pytest
from proxion_keyring.registry import AppRegistry

def test_registry_lookup(tmp_path):
    # Create a temporary registry file
    reg_file = tmp_path / "registry.json"
    data = {
        "apps": {
            "test-app": {"path": "test/path"}
        }
    }
    reg_file.write_text(json.dumps(data))
    
    registry = AppRegistry(str(reg_file))
    
    # Test lookup
    assert registry.get_subpath("test-app") == "test/path"
    # Test fallback
    assert registry.get_subpath("unknown") == "apps/unknown"

def test_app_path_resolution(tmp_path):
    # Create a fake integrations structure
    integrations = tmp_path / "integrations"
    integrations.mkdir()
    (integrations / "app1").mkdir()
    (integrations / "app2-integration").mkdir()
    
    reg_file = integrations / "registry.json"
    reg_file.write_text("{}")
    
    registry = AppRegistry(str(reg_file))
    
    # Verify resolution
    assert registry.get_app_path("app1").endswith("app1")
    assert registry.get_app_path("app2").endswith("app2-integration")
    assert registry.get_app_path("missing") is None
