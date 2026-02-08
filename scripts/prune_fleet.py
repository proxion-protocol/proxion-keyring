import os
import shutil
import sys

# The "Sovereign 25" - Core Fleet and Requested Keeps
KEEP_LIST = [
    # Active Core
    "adguard-integration",
    "bazarr-integration",
    "calibre-integration",
    "freshrss-integration",
    "immich-integration",
    "jellyfin-integration",
    "lidarr-integration",
    "navidrome-integration",
    "prowlarr-integration",
    "radarr-integration",
    "readarr-integration",
    "searxng-integration",
    "sonarr-integration",
    "syncthing-integration",
    "vaultwarden-integration",
    "watchtower-integration",
    
    # Parked Keeps
    "audiobookshelf-integration",
    "tautulli-integration",
    "tdarr-integration",
    "transmission-integration",
    "homebox-integration",
    "steam-headless-integration",
    "pialert-integration",
    "jellyseerr-integration",
    "pairdrop-integration"
]

INTEGRATIONS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../integrations"))

def prune(dry_run=True):
    if not os.path.exists(INTEGRATIONS_ROOT):
        print(f"Error: Root {INTEGRATIONS_ROOT} not found.")
        return

    print(f"--- Fleet Pruning Audit ({'DRY RUN' if dry_run else 'DESTRUCTIVE'}) ---")
    
    all_dirs = [d for d in os.listdir(INTEGRATIONS_ROOT) if os.path.isdir(os.path.join(INTEGRATIONS_ROOT, d))]
    to_remove = [d for d in all_dirs if d not in KEEP_LIST]
    
    print(f"Total Integrations Found: {len(all_dirs)}")
    print(f"Integrations to Prune:   {len(to_remove)}")
    print(f"Integrations to Keep:    {len(all_dirs) - len(to_remove)}")
    print("-" * 40)

    for d in to_remove:
        path = os.path.join(INTEGRATIONS_ROOT, d)
        if dry_run:
            print(f"[DRY] Would remove: {d}")
        else:
            print(f"[REMOVING] {d}...")
            try:
                shutil.rmtree(path)
            except Exception as e:
                print(f"[ERROR] Failed to remove {d}: {e}")

    if not dry_run:
        print("\nPruning complete.")
    else:
        print("\nDry run finished. No files were deleted.")

if __name__ == "__main__":
    is_dry = "--execute" not in sys.argv
    prune(dry_run=is_dry)
