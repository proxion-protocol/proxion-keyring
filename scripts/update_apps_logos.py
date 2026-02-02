
import json
import os

APPS_JSON_PATH = r"c:\Users\hobo\Desktop\Proxion\proxion-keyring\dashboard\src\data\apps.json"

# Mapping of ID -> SimpleIcons Slug
SLUG_MAP = {
    "adguard-integration": "adguard",
    "archivebox-integration": "internetarchive",
    "calibre-integration": "calibre", 
    "changedetection-integration": "changedetection", # Correct slug
    "cryptpad-integration": "cryptpad", 
    "firefly-integration": "fireflyiii",
    "freshrss-integration": "freshrss", # Correct slug
    "ghost-integration": "ghost",
    "gitea-integration": "gitea",
    "homarr-integration": "homarr", # Now in simple-icons!
    "home-assistant-integration": "homeassistant",
    "homebridge-integration": "homebridge",
    "immich-integration": "immich", 
    "jellyfin-integration": "jellyfin",
    "joplin-integration": "joplin",
    "mastodon-integration": "mastodon",
    "matrix-integration": "matrix",
    "navidrome-integration": "navidrome", # check if exists, otherwise musicbrainz
    "nextcloud-integration": "nextcloud",
    "overseerr-integration": "plex", 
    "paperless-integration": "paperlessngx", 
    "pihole-integration": "pihole",
    "sonarr-integration": "sonarr",
    "radarr-integration": "radarr",
    "lidarr-integration": "lidarr",
    "prowlarr-integration": "prowlarr",
    "bazarr-integration": "bazarr",
    "readarr-integration": "readarr",
    "audiobookshelf-integration": "audiobookshelf", 
    "vikunja-integration": "vikunja", 
    "stirling-pdf-integration": "stirling-pdf", 
    "mealie-integration": "mealie", 
    "silverbullet-integration": "silverbullet",
    "kiwix-integration": "kiwix",
    "pairdrop-integration": "pairdrop", 
    "transmission-integration": "transmission",
    "tautulli-integration": "tautulli",
    "thunderbird-integration": "thunderbird",
    "vaultwarden-integration": "vaultwarden",
    "wallabag-integration": "wallabag", 
    "kopia-integration": "kopia", 
    "pialert-integration": "pi-alert",
    "tdarr-integration": "tdarr",
    "searxng-integration": "searxng",
    "mattermost-integration": "mattermost",
    "kasm-integration": "kasm",
    "it-tools-integration": "it-tools",
    "cyberchef-integration": "cyberchef",
    "jitsi-integration": "jitsi",
    "monica-integration": "monica", 
    "ghostfolio-integration": "ghostfolio",
    "wallos-integration": "wallos", 
    "netdata-integration": "netdata",
    "speedtest-tracker-integration": "speedtest-tracker",
    "portainer-integration": "portainer",
    "authelia-integration": "authelia",
    "watchtower-integration": "watchtower",
    "syncthing-integration": "syncthing",
    "filebrowser-integration": "filebrowser",
    "linkwarden-integration": "linkwarden",
    "actual-integration": "actual-budget",
    "uptime-kuma-integration": "uptime-kuma",
    "steam-headless-integration": "steam",
    "romm-integration": "romm",
    "emulatorjs-integration": "emulatorjs",
    "pterodactyl-integration": "pterodactyl",
    "homeassistant-integration": "homeassistant",
    "lemmy-integration": "lemmy",
    "firefox-integration": "firefox",
    "bluesky-pds-integration": "bluesky",
    "pixelfed-integration": "pixelfed",
    "wordpress-integration": "wordpress"
}

def update_apps():
    with open(APPS_JSON_PATH, "r") as f:
        data = json.load(f)

    for app in data:
        if app["id"] in SLUG_MAP:
            app["logo_slug"] = SLUG_MAP[app["id"]]
        # Standardize button labels or other metadata here if needed

    with open(APPS_JSON_PATH, "w") as f:
        json.dump(data, f, indent=4)
    
    print(f"Updated {len(data)} apps with logo slugs.")

if __name__ == "__main__":
    update_apps()
