import os
import re

root_dir = r"c:\Users\hobo\Desktop\Proxion\integrations"

app_map = {
    "adguard-integration": "network/adguard",
    "archivebox-integration": "web/archive",
    "calibre-integration": "knowledge/calibre",
    "changedetection-integration": "web/monitor",
    "cryptpad-integration": "office/cryptpad",
    "firefly-integration": "finance/firefly",
    "freshrss-integration": "web/freshrss",
    "ghost-integration": "web/ghost",
    "gitea-integration": "dev/gitea",
    "home-assistant-integration": "iot/ha",
    "homebridge-integration": "iot/homebridge",
    "immich-integration": "media/immich",
    "jellyfin-integration": "media/jellyfin",
    "joplin-integration": "knowledge/joplin",
    "mastodon-integration": "social/mastodon",
    "matrix-integration": "social/matrix",
    "navidrome-integration": "media/navidrome",
    "nextcloud-integration": "cloud/nextcloud",
    "paperless-integration": "docs/paperless",
    "pihole-integration": "network/pihole",
    "thunderbird-integration": "mail/thunderbird",
    "vaultwarden-integration": "security/vaultwarden",
    "wallabag-integration": "web/wallabag",
    "wordpress-integration": "web/wordpress"
}

for app_folder, subpath in app_map.items():
    folder_path = os.path.join(root_dir, app_folder)
    
    # 1. Fix YML Paths
    override_path = os.path.join(folder_path, "docker-compose.override.yml")
    if os.path.exists(override_path):
        with open(override_path, "r") as f:
            content = f.read()
        
        # Match P:/app/subfolder/app/subfolder and collapse it to P:/app/subfolder
        # e.g. P:/social/mastodon/social/mastodon/ -> P:/social/mastodon/
        # This is a bit tricky with regex, let's use a simpler string replace if we can detect the duplication
        double_path = f"P:/{subpath}/{subpath}"
        if double_path in content:
            print(f"Fixing double path in {override_path}")
            content = content.replace(double_path, f"P:/{subpath}")
            with open(override_path, "w") as f:
                f.write(content)

    # 2. Fix Start Script Deduplication
    for name in os.listdir(folder_path):
        if name.startswith("start_") and name.endswith(".py"):
            path = os.path.join(folder_path, name)
            with open(path, "r") as f:
                content = f.read()
            
            # Remove duplicate is_mounted
            content = re.sub(r'def is_mounted\(drive\):.*?def is_mounted\(drive\):', 'def is_mounted(drive):', content, flags=re.DOTALL)
            
            # Clean up potential duplicate run_mount or messy artifacts
            # Ensure only one is_mounted exists
            if content.count("def is_mounted(drive):") > 1:
                 content = content.replace("def is_mounted(drive):", "TEMP_HOLDER", 1)
                 content = content.replace("def is_mounted(drive):", "")
                 content = content.replace("TEMP_HOLDER", "def is_mounted(drive):")
                 
            print(f"Cleaning up {path}")
            with open(path, "w") as f:
                 f.write(content)
