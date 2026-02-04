import json
import os

# Config lives in the absolute proxion-keyring root (one level up from this file's folder)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_PATH = os.path.join(REPO_ROOT, "proxion_config.json")

DEFAULT_CONFIG = {
    "stash_sources": [
        {"name": "Default Stash", "path": "/stash/", "primary": True}
    ]
}

def load_config():
    print(f"[Config] Loading from: {CONFIG_PATH}")
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                config = json.load(f)
                # Migration: if old 'pod_path' exists, convert to stash_sources
                if "pod_path" in config and "stash_sources" not in config:
                    config["stash_sources"] = [
                        {"name": "Migrated Source", "path": config["pod_path"], "primary": True}
                    ]
                    del config["pod_path"]
                return {**DEFAULT_CONFIG, **config}
        except Exception as e:
            print(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    print(f"[Config] Saving to: {CONFIG_PATH}")
    try:
        os.makedirs(REPO_ROOT, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
            return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False
