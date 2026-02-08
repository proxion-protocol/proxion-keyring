"""
Fleet Parking Script - Proxion V8.1
Stops and parks non-essential integrations to establish stable core fleet.
"""
import os
import subprocess
from pathlib import Path

INTEGRATIONS_DIR = Path(r"C:\Users\hobo\Desktop\Proxion\integrations")

# Core fleet to KEEP active
CORE_FLEET = {
    "authentik-integration",
    "vaultwarden-integration",
    "adguard-integration",
    "jellyfin-integration",
    "sonarr-integration",
    "radarr-integration",
    "prowlarr-integration",
    "bazarr-integration",
    "lidarr-integration",
    "readarr-integration",
    "calibre-integration",
    "navidrome-integration",
    "immich-integration",
    "freshrss-integration",
    "searxng-integration",
    "syncthing-integration",
    "watchtower-integration",
}

def park_integration(integration_dir: Path):
    """Stop containers and rename docker-compose.yml to .parked"""
    compose_file = integration_dir / "docker-compose.yml"
    parked_file = integration_dir / "docker-compose.parked"
    
    if not compose_file.exists():
        # Already parked or no compose file
        if parked_file.exists():
            return f"{integration_dir.name}: Already parked"
        return f"{integration_dir.name}: No compose file"
    
    # Stop containers
    try:
        result = subprocess.run(
            ["docker", "compose", "down"],
            cwd=integration_dir,
            capture_output=True,
            timeout=30,
            text=True
        )
        if result.returncode != 0:
            print(f"  Warning: {integration_dir.name} stop had errors: {result.stderr[:100]}")
    except subprocess.TimeoutExpired:
        return f"{integration_dir.name}: Timeout stopping (forced park)"
    except Exception as e:
        return f"{integration_dir.name}: Failed to stop ({str(e)[:50]})"
    
    # Rename to .parked
    try:
        compose_file.rename(parked_file)
        return f"{integration_dir.name}: ✅ PARKED"
    except Exception as e:
        return f"{integration_dir.name}: Failed to rename ({str(e)[:50]})"

def main():
    print("=" * 80)
    print("PROXION FLEET PARKING - V8.1")
    print("=" * 80)
    print(f"\nCore Fleet Size: {len(CORE_FLEET)} integrations")
    print(f"Scanning: {INTEGRATIONS_DIR}\n")
    
    results = []
    parked_count = 0
    active_count = 0
    
    for integration_dir in sorted(INTEGRATIONS_DIR.iterdir()):
        if not integration_dir.is_dir():
            continue
        
        if integration_dir.name.startswith('.'):
            continue
            
        if integration_dir.name in CORE_FLEET:
            results.append(f"{integration_dir.name}: 🟢 ACTIVE (Core Fleet)")
            active_count += 1
            continue
        
        result = park_integration(integration_dir)
        results.append(result)
        if "PARKED" in result:
            parked_count += 1
    
    print("\n".join(results))
    print("\n" + "=" * 80)
    print(f"✅ Parked: {parked_count} integrations")
    print(f"🟢 Active: {active_count} integrations (Core Fleet)")
    print(f"📊 Total: {parked_count + active_count} integrations processed")
    print("=" * 80)

if __name__ == "__main__":
    main()
