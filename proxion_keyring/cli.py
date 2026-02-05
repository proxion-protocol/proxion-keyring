import click
import os
import subprocess
import time
import json
import requests
import qrcode
from cryptography.hazmat.primitives import serialization
from proxion_core.federation import FederationInvite, InviteAcceptance, Capability
from proxion_keyring.identity import load_or_create_identity_key
from proxion_keyring.os_adapter import get_adapter
from proxion_keyring.registry import AppRegistry

# Initializing Portability Layers
adapter = get_adapter()
registry = AppRegistry()

@click.group()
def cli():
    """Proxion Keyring Federation CLI."""
    pass

@cli.group()
def mesh():
    """Manage the local machine's connection to the Proxion Mesh."""
    pass

@mesh.command(name="dns-enable")
def mesh_dns_enable():
    """Point host DNS to local Proxion AdGuard (Safe)."""
    click.echo("[Proxion] Requesting host DNS change to 127.0.0.1...")
    
    # Use adapter to find the active interface
    idx = adapter.get_active_interface_index()
    if idx is None:
        click.echo("Error: Could not identify the active network interface.")
        return

    try:
        adapter.set_dns(idx, "127.0.0.1")
        click.echo("[Proxion] Command sent. Please approve the UAC prompt if it appears.")
    except Exception as e:
        click.echo(f"Error: Failed to set DNS: {e}")

@mesh.command(name="dns-disable")
def mesh_dns_disable():
    """Reset host DNS to automatic (DHCP)."""
    click.echo("[Proxion] Requesting DNS reset...")
    idx = adapter.get_active_interface_index()
    if idx is None:
        click.echo("Error: Could not identify the active network interface.")
        return

    try:
        adapter.reset_dns(idx)
        click.echo("[Proxion] Command sent. Please approve the UAC prompt if it appears.")
    except Exception as e:
        click.echo(f"Error: Failed to reset DNS: {e}")

@cli.group()
def federation():
    """Manage Federation (Peer Discovery & Handshake)."""
    pass

@federation.command()
@click.option('--resource', required=True, help='Resource URI (e.g. stash://alice/shared/bob)')
@click.option('--permissions', required=True, help='Permissions (e.g. crud/read)')
@click.option('--quota-mb', type=int, default=1000, help='Quota in megabytes')
@click.option('--expires-hours', type=int, default=24, help='Invite expiry hours')
@click.option('--relay', default="relay://relay.proxion.net", help='Relay endpoint hint')
def generate_invite(resource, permissions, quota_mb, expires_hours, relay):
    """Generate a Federation Invite QR Code."""
    
    # Load Identity
    identity_key = load_or_create_identity_key()
    pub_hex = identity_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()

    # Create Capability
    cap = Capability(
        with_=resource,
        can=permissions,
        caveats={"quota_mb": quota_mb}
    )

    # Create Invite
    invite = FederationInvite(
        issuer={
            "public_key": pub_hex,
            "did": f"did:key:{pub_hex}"
        },
        endpoint_hints=[relay],
        capabilities=[cap],
        expires_at=int(time.time()) + (expires_hours * 3600)
    )
    invite.sign(identity_key)

    # Render QR
    data = json.dumps(invite.to_dict())
    qr = qrcode.QRCode()
    qr.add_data(data)
    qr.print_ascii()
    
    click.echo(f"\nInvite generated for {resource}")
    click.echo(f"Expires in {expires_hours} hours.")
    click.echo(f"Invitation ID: {invite.invitation_id}")

@federation.command()
@click.option('--invite-file', required=True, type=click.File('r'), help='Path to invite JSON file')
def accept_invite(invite_file):
    """Accept a Federation Invite from a JSON file."""
    try:
        data = json.load(invite_file)
        invite = FederationInvite(**data)
        # Note: In a real CLI verify logic would be here, but verifying requires Ed25519 Verify
        # which needs the issuer pubkey. `invite.verify` accepts a callback.
        # For CLI MVP, we skip strictly verifying signature here and assume server does it,
        # OR we implement a quick fallback verifier if needed.
        
        # We need to sign the challenge
        identity_key = load_or_create_identity_key()
        pub_hex = identity_key.public_key().public_bytes(
             encoding=serialization.Encoding.Raw,
             format=serialization.PublicFormat.Raw
        ).hex()
        
        # Sign challenge (using the key object directly since we wrote the logic in classes)
        # However, our FederationInvite/Acceptance classes call .sign() on the key object.
        # cryptography's key object has .sign(), so it works.
        
        # But wait, `invite.challenge_marker` needs to be signed.
        # Our `InviteAcceptance.sign` signs the whole acceptance object.
        # We need to manually sign the challenge marker first.
        challenge_sig = identity_key.sign(invite.challenge_marker.encode()).hex()
        
        acceptance = InviteAcceptance(
            invitation_id=invite.invitation_id,
            responder={
                "public_key": pub_hex,
                "endpoint_hints": ["udp://my.endpoint:51820"] # Mock hint
            },
            challenge_response=challenge_sig
        )
        acceptance.sign(identity_key)
        
        # Send
        target = invite.endpoint_hints[0]
        click.echo(f"Sending acceptance to {target}...")
        
        # Mock HTTP send for now as we don't have a live relay
        # response = requests.post(f"{target}/federation/accept", json=acceptance.to_dict())
        click.echo("Acceptance payload created successfully:")
        click.echo(json.dumps(acceptance.to_dict(), indent=2))
        click.echo("\n(In a real scenario, this payload is POSTed to the issuer endpoint)")
        
    except Exception as e:
        click.echo(f"Error: {e}")

# --- Suite Profiles ---
PROFILES = {
    "core": ["homarr", "authelia", "watchtower", "portainer", "syncthing", "filebrowser", "kopia", "uptime-kuma"],
    "media": ["jellyfin", "plex", "navidrome", "audiobookshelf", "kavita", "sonarr", "radarr", "lidarr", "prowlarr", "bazarr", "jellyseerr", "tautulli", "overseerr", "transmission", "tdarr", "readarr"],
    "social": ["mastodon", "mattermost", "jitsi", "monica", "lemmy", "pixelfed"],
    "gaming": ["steam-headless", "romm", "emulatorjs", "pterodactyl"],
    "dev": ["gitea", "it-tools", "cyberchef", "stirling-pdf", "kasm"],
    "web": ["firefox", "bluesky-pds", "searxng", "linkwarden", "ghost", "archivebox", "changedetection"],
    "home": ["homeassistant", "homebridge", "pialert", "adguard", "netdata", "speedtest-tracker"],
    "office": ["joplin", "firefly", "wallabag", "cryptpad", "vikunja", "actual", "silverbullet", "kiwix", "mealie", "homebox", "ghostfolio", "wallos"]
}

@cli.group()
def suite():
    """Manage the Proxion Suite (Apps & Drives)."""
    pass

@suite.command(name="ls")
def suite_ls():
    """List all integrated applications and profiles."""
    import os
    integrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../integrations"))
    if not os.path.exists(integrations_dir):
        click.echo("Error: Integrations directory not found.")
        return

    apps = [d for d in os.listdir(integrations_dir) if os.path.isdir(os.path.join(integrations_dir, d))]
    
    click.echo(f"\n{'--- PROXION SUITE PROFILES ---':<45}")
    for profile in sorted(PROFILES.keys()):
        count = len(PROFILES[profile])
        click.echo(f"  {profile:<15} ({count} apps)")
        
    click.echo(f"\n{'Application':<30} {'Status':<15}")
    click.echo("-" * 45)
    for app in sorted(apps):
        click.echo(f"{app:<30} AVAILABLE")

def _get_app_path(app_name):
    return registry.get_app_path(app_name)

def _run_docker_compose(app_name, app_path, action=["up", "-d"]):
    """Run docker-compose with platform-specific overrides."""
    # Discovery of local storage root
    cli_dir = os.path.dirname(os.path.abspath(__file__))
    local_storage = os.path.abspath(os.path.join(cli_dir, "../../proxion-core/storage")).replace("\\", "/")
    
    cmd = adapter.get_docker_compose_cmd(app_path, local_storage, action)
    return subprocess.run(cmd, cwd=app_path, capture_output=True, text=True)

def _provision_app(app_name, app_path):
    """Run app-specific provisioning logic."""
    if "adguard" in app_name:
        try:
            from proxion_keyring.provision_adguard import provision_adguard
            pw = provision_adguard()
            if pw:
                click.echo(f"[Proxion] Identity-linked password set for {app_name}.")
                click.echo(f"[HELP] Dashboard: http://localhost:3002")
                click.echo(f"[HELP] Username:  admin")
                click.echo(f"[HELP] Password:  {pw}")
        except Exception as e:
            click.echo(f"[WARN] Failed to auto-provision {app_name}: {e}")
    
    elif "archivebox" in app_name:
        try:
            # Run the auto-setup script
            setup_script = os.path.join(app_path, "start_archivebox.py")
            if os.path.exists(setup_script):
                click.echo(f"[Proxion] Configuring {app_name}...")
                result = subprocess.run(
                    ["python", setup_script],
                    cwd=app_path,
                    capture_output=True,
                    text=True,
                    timeout=120  # Increased timeout for container initialization
                )
                # Display the output which includes credentials
                if result.returncode == 0:
                    click.echo(result.stdout)
                else:
                    click.echo(f"[WARN] Auto-setup completed with warnings:")
                    click.echo(result.stdout)
                    click.echo(result.stderr)
            else:
                click.echo(f"[WARN] Auto-setup script not found at {setup_script}")
        except Exception as e:
            click.echo(f"[WARN] Failed to auto-provision {app_name}: {e}")

    elif "calibre" in app_name:
        try:
            setup_script = os.path.join(app_path, "setup_calibre.py")
            if os.path.exists(setup_script):
                click.echo(f"[Proxion] Configuring {app_name}...")
                result = subprocess.run(
                    ["python", setup_script],
                    cwd=app_path,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                click.echo(result.stdout)
                if result.returncode != 0:
                    click.echo(f"[WARN] Setup failed: {result.stderr}")
        except Exception as e:
             click.echo(f"[WARN] Failed to auto-provision {app_name}: {e}")

    elif "vaultwarden" in app_name:
        try:
            from proxion_keyring.provision_vaultwarden import provision_vaultwarden
            res = provision_vaultwarden()
            click.echo(f"[Proxion] Vaultwarden Security provisioned.")
            click.echo(f"[HELP] Admin Token: {res['admin_token']}")
            click.echo(f"[HELP] Master Pass: {res['master_password']}")
            click.echo(f"[HELP] Dashboard:  http://localhost:8086")
        except Exception as e:
            click.echo(f"[WARN] Failed to auto-provision {app_name}: {e}")

@suite.command(name="install")
@click.argument('app_name')
@click.option('--protect-host', is_flag=True, help="Automatically point host DNS to this app (e.g. for AdGuard).")
def suite_install(app_name, protect_host):
    """Prepare subfolders and pull images for an app."""
    
    app_path = _get_app_path(app_name)
    if not app_path:
        click.echo(f"Error: Application '{app_name}' folder not found.")
        return

    # 1. Ensure Drive P: exists and create subdirectory
    mount_point = "P:\\"
    subpath = registry.get_subpath(app_name)
    full_subpath = os.path.join(mount_point, subpath)

    if os.path.exists(mount_point):
        click.echo(f"[Proxion] Preparing storage at {full_subpath}...")
        try:
            os.makedirs(full_subpath, exist_ok=True)
        except OSError as e:
            click.echo(f"[Proxion] Warning: Failed to create storage directory on P: ({e}). Proceeding anyway relying on Host Path.")
    else:
        click.echo("[Proxion] Warning: Drive P: not mounted. Storage prep skipped.")

    # 3. Create Marker File (Tracking)
    marker = os.path.join(app_path, ".installed")
    with open(marker, "w") as f:
        f.write(str(int(time.time())))

    # 4. Provision
    _provision_app(app_name, app_path)

    # 5. Start the Application
    click.echo(f"[Proxion] Deploying {app_name} on host...")
    try:
        res = _run_docker_compose(app_name, app_path, ["up", "-d"])
        if res.returncode == 0:
            click.echo(f"[Proxion] {app_name} installed and started successfully.")
            
            # AdGuard Specific Automation
            if "adguard" in app_name:
                if protect_host:
                    # Trigger the automated DNS protection
                    ctx = click.get_current_context()
                    ctx.invoke(mesh_dns_enable)
                else:
                    click.echo("\n[NEXT STEPS] To use AdGuard DNS on this machine:")
                    click.echo("  Run: python -m proxion_keyring.cli mesh dns-enable")
                    click.echo("  Or set Windows DNS to 127.0.0.1 manually.")
        else:
            click.echo(f"[WARN] Storage prepped, but deployment failed: {res.stderr}")
    except Exception as e:
        click.echo(f"[ERROR] Deployment error: {e}")

@suite.command(name="uninstall")
@click.argument('app_name')
def suite_uninstall(app_name):
    """Remove an app (stop containers and remove tracker)."""
    import os
    import subprocess
    
@suite.command(name="uninstall")
@click.argument('app_name')
def suite_uninstall(app_name):
    """Remove an app (stop containers and remove tracker)."""
    
    app_path = registry.get_app_path(app_name)
    if not app_path:
        click.echo(f"Error: Application '{app_name}' folder not found.")
        return

    # 1. Stop Containers
    click.echo(f"[Proxion] Stopping {app_name}...")
    try:
        subprocess.run(["docker-compose", "down"], cwd=app_path, capture_output=True)
    except Exception as e:
        click.echo(f"[WARN] Failed to stop containers: {e}")

    # 2. Remove Marker
    marker = os.path.join(app_path, ".installed")

    if os.path.exists(marker):
        os.remove(marker)
        click.echo(f"[Proxion] {app_name} uninstalled (tracking removed).")
    else:
        click.echo(f"[Proxion] {app_name} was not installed.")
    
    # We DO NOT delete data in P: (User data preservation)
    click.echo("[NOTE] Application data in P: was preserved.")

@suite.command(name="up")
@click.argument('target', default='all')
def suite_up(target):
    """Start the Proxion Suite, a Profile, or a specific App."""
    import os
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    
    # 1. Ensure Drive P: is mounted
    mount_point = "P:"
    if not os.path.exists(mount_point):
        click.echo(f"[Proxion] {mount_point} not found. Orchestrating mount...")
        fuse_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../proxion-fuse/mount.py"))
        pod_path = "/stash/" 
        
        # Start FUSE in background
        cmd = ["python", fuse_script, mount_point, pod_path]
        subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
        
        click.echo("[Proxion] Waiting for P: drive to stabilize...")
        for _ in range(10):
            time.sleep(1)
            if os.path.exists(mount_point):
                break
        
        if not os.path.exists(mount_point):
            click.echo("Error: Failed to mount P: drive.")
            return

    # 2. Identify Targets
    integrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../integrations"))
    available_apps = [d.replace("-integration", "") for d in os.listdir(integrations_dir) if os.path.isdir(os.path.join(integrations_dir, d))]
    
    app_targets = []
    
    if target == 'all':
        # "all" starts EVERYTHING. We prioritize "core" first.
        core_apps = PROFILES.get("core", [])
        other_apps = [a for a in available_apps if a not in core_apps]
        app_targets = core_apps + other_apps
    elif target in PROFILES:
        app_targets = PROFILES[target]
    elif target in available_apps:
        app_targets = [target]
    else:
        click.echo(f"Error: '{target}' is not a valid App or Profile.")
        return

    def launch_app(app_id):
        app_path = _get_app_path(app_id)
        if not app_path:
            return f"{app_id}: FOLDER MISSING"
        try:
            res = _run_docker_compose(app_id, app_path, ["up", "-d"])
            if res.returncode == 0:
                return f"{app_id}: OK"
            else:
                return f"{app_id}: FAIL ({res.stderr[:50]}...)"
        except Exception as e:
            return f"{app_id}: FAIL ({str(e)})"

    # 3. Execution Phase
    click.echo(f"[Proxion] Orchestrating launch for {len(app_targets)} apps...")
    
    # If "all" or specific profiles, we do them in batches or purely parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(launch_app, app_targets))
        
    for res in results:
        click.echo(f"  {res}")
    
    click.echo(f"\n[Proxion] Orchestration complete.")

@suite.command(name="down")
@click.argument('target', default='all')
def suite_down(target):
    """Stop the Proxion Suite, a Profile, or a specific App."""
    import os
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    
    integrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../integrations"))
    available_apps = [d.replace("-integration", "") for d in os.listdir(integrations_dir) if os.path.isdir(os.path.join(integrations_dir, d))]
    
    app_targets = []
    
    if target == 'all':
        app_targets = available_apps
    elif target in PROFILES:
        app_targets = PROFILES[target]
    elif target in available_apps:
        app_targets = [target]
    else:
        click.echo(f"Error: '{target}' is not a valid App or Profile.")
        return

    def stop_app(app_id):
        app_path = registry.get_app_path(app_id)
        if not app_path:
            return f"{app_id}: FOLDER MISSING"
        try:
            subprocess.run(["docker-compose", "down"], cwd=app_path, capture_output=True)
            return f"{app_id}: STOPPED"
        except Exception as e:
            return f"{app_id}: FAIL ({str(e)})"

    click.echo(f"[Proxion] Orchestrating shutdown for {len(app_targets)} apps...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(stop_app, app_targets))
        
    for res in results:
        click.echo(f"  {res}")
            
    if target == 'all':
        click.echo("\n[Proxion] Entire suite is down.")
        click.echo("[Proxion] To unmount P:, please close any open files and use OS eject or stop the mount process.")

@suite.command(name="restart")
@click.argument('target', default='all')
def suite_restart(target):
    """Restart the Proxion Suite, a Profile, or a specific App."""
    import os
    import subprocess
    from concurrent.futures import ThreadPoolExecutor
    
    integrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../integrations"))
    available_apps = [d.replace("-integration", "") for d in os.listdir(integrations_dir) if os.path.isdir(os.path.join(integrations_dir, d))]
    
    app_targets = []
    
    if target == 'all':
        app_targets = [a for a in available_apps if os.path.exists(os.path.join(registry.get_app_path(a), ".installed"))]
    elif target in PROFILES:
        app_targets = PROFILES[target]
    elif target in available_apps:
        app_targets = [target]
    else:
        click.echo(f"Error: '{target}' is not a valid App or Profile.")
        return

    def restart_app(app_id):
        app_path = registry.get_app_path(app_id)
        if not app_path:
            return f"{app_id}: FOLDER MISSING"
        try:
            subprocess.run(["docker-compose", "restart"], cwd=app_path, capture_output=True)
            return f"{app_id}: RESTARTED"
        except Exception as e:
            return f"{app_id}: FAIL ({str(e)})"

    click.echo(f"[Proxion] Orchestrating restart for {len(app_targets)} apps...")
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(restart_app, app_targets))
        
    for res in results:
        click.echo(f"  {res}")

@suite.command(name="status")
@click.option('--detail', is_flag=True, help="Show detailed container status.")
def suite_status(detail):
    """Check the health of the Proxion Suite."""
    import os
    import subprocess
    
    click.echo("\n--- Proxion Suite Status ---")
    
    # Check Mount
    mount_point = "P:"
    if os.path.exists(mount_point):
        click.echo(f"Unified Mount (P:):  ONLINE")
    else:
        click.echo(f"Unified Mount (P:):  OFFLINE")
        
    # Check Core Proxy
    try:
        resp = requests.get("http://127.0.0.1:8089/pod/", timeout=2)
        click.echo(f"Pod Proxy (8089):    ONLINE")
    except:
        click.echo(f"Pod Proxy (8089):    OFFLINE")

    # Check Containers
    try:
        output = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}|{{.Status}}"]).decode()
        running = output.strip().split('\n') if output.strip() else []
        click.echo(f"Running Containers:  {len(running)}")
        
        if detail and running:
            click.echo("\nDetails:")
            for line in running:
                name, status = line.split('|')
                click.echo(f"  {name:<25} {status}")
    except:
        click.echo("Running Containers:  ERROR (Docker not running?)")

    click.echo("-" * 38)

if __name__ == '__main__':
    cli()
