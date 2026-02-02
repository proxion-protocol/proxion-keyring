import os

root_dir = r"c:\Users\hobo\Desktop\Proxion\integrations"

# Mapping of existing folders to their new P: subpaths
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

# 1. Update Override YMLs
for app_folder, subpath in app_map.items():
    folder_path = os.path.join(root_dir, app_folder)
    override_path = os.path.join(folder_path, "docker-compose.override.yml")
    
    if os.path.exists(override_path):
        with open(override_path, "r") as f:
            lines = f.readlines()
        
        new_lines = []
        import re
        for line in lines:
            # Match " - DRIVE:/" or " - DRIVE:\" or " - DRIVE: "
            # And replace it with " - P:/subpath/"
            new_line = re.sub(r'([ \t]- )[A-Z]:(?=[/\\]| )', rf'\1P:/{subpath}', line)
            new_lines.append(new_line)
        
        print(f"Updating {override_path}")
        with open(override_path, "w") as f:
             f.writelines(new_lines)

# 2. Update Start Scripts
for app_folder, subpath in app_map.items():
    folder_path = os.path.join(root_dir, app_folder)
    if not os.path.exists(folder_path): continue
    
    for name in os.listdir(folder_path):
        if name.startswith("start_") and name.endswith(".py"):
            path = os.path.join(folder_path, name)
            with open(path, "r") as f:
                content = f.read()
            
            # Update MOUNT_POINT and POD_PATH
            import re
            content = re.sub(r'MOUNT_POINT = "[A-Z]:"', 'MOUNT_POINT = "P:"', content)
            content = re.sub(r'POD_PATH = "[^"]+"', 'POD_PATH = "/stash/"', content)
            
            # Refined run_mount with Presence Check and correct relative paths
            # We assume the script is in /integrations/APP-integration/start_*.py
            # So ../../proxion-fuse/mount.py is correct
            presence_check = """
def is_mounted(drive):
    return os.path.exists(drive)

def run_mount():
    \"\"\"Start the FUSE mount on Drive P:\"\"\"
    if is_mounted(MOUNT_POINT):
        print(f"[Proxion] {MOUNT_POINT} is already mounted. Skipping.")
        return None
        
    print(f"[Proxion] Mounting Pod {POD_PATH} to {MOUNT_POINT} ...")
    fuse_script = os.path.abspath(os.path.join(os.getcwd(), "../../proxion-fuse/mount.py"))
    cmd = ["python", fuse_script, MOUNT_POINT, POD_PATH]
    return subprocess.Popen(cmd)
"""
            # Replace the old run_mount block
            content = re.sub(r'def run_mount\(\):.*?(?=\ndef start_docker)', presence_check, content, flags=re.DOTALL)
            
            # Update main to handle None mount process safely
            content = content.replace('if mount_process.poll() is not None:', 'if mount_process and mount_process.poll() is not None:')
            
            print(f"Updating {path}")
            with open(path, "w") as f:
                 f.write(content)
