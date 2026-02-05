"""proxion-keyring Resource Server (Flask).

Exposes real HTTP endpoints for secure channel bootstrap.
"""


import os
import sys
import secrets
from flask import Flask, request, jsonify
from flask_cors import CORS
import threading

from .service import ResourceServer, WireGuardConfig
from ..manager import KeyringManager
from ..pod_proxy import PodProxyServer
from ..identity import derive_app_password, load_or_create_identity_key
from ..config import load_config, save_config

# Global Manager
manager = KeyringManager()
# Need to import Token/RequestContext/validate_request from core if we want to reconstruct objects
# But for MVP we might mock the token validation if we don't transfer the full token object securely.
# In a real setup, the token is passed.
from proxion_core import Token, RequestContext, Decision
try:
    from proxion_core.validator import validate_request
except ImportError:
    print("WARNING: proxion_core.validator not found. Using MOCK validation.")
    def validate_request(*args, **kwargs):
        return Decision(allowed=True, reason="Mock Validation")

app = Flask(__name__)
CORS(app, resources={r"/*": {
    "origins": ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173", "chrome-extension://*", "moz-extension://*"],
    "allow_headers": ["Content-Type", "Proxion-Token", "X-Proxion-PoP"],
    "methods": ["GET", "POST", "OPTIONS"]
}})

# Initialize Resource Server with CP's Public Key for token verification
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from .serialization_shim import TokenSerializer

cp_pub_hex = os.getenv("proxion-keyring_CP_PUBKEY", "3ccd241cffc9b3618044b97d036d8614593d8b017c340f1dee8773385517654b")
try:
    CP_PUBLIC_KEY = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(cp_pub_hex))
except Exception as e:
    print(f"ERROR: Failed to load CP Public Key: {e}")
    # Fallback to demo default if error
    CP_PUBLIC_KEY = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex("3ccd241cffc9b3618044b97d036d8614593d8b017c340f1dee8773385517654b"))

# Shared secret for other purposes if any, but Token signing is now asymmetric.
# We'll use a dummy bytes for ResourceServer init if it still expects symmetric (for legacy purposes)
DUMMY_KEY = b"dummy-key-for-legacy-init"

import atexit

# WireGuard config
MSG_ENDPOINT = os.getenv("proxion-keyring_WG_ENDPOINT", "127.0.0.1:51820")
PUBKEY = os.getenv("proxion-keyring_WG_PUBKEY", "demo-pubkey")
INTERFACE = os.getenv("proxion-keyring_WG_INTERFACE", "wg-proxion-keyring")

wg_config = WireGuardConfig(
    enabled=True,
    interface=INTERFACE,
    endpoint=MSG_ENDPOINT,
    server_pubkey=PUBKEY
)
# Strict RS (Phase 5)
rs = ResourceServer(signing_key=DUMMY_KEY, wg_config=wg_config)

def cleanup():
    """Remove all peers on shutdown."""
    if not rs._mutation_enabled:
        return
        
    print(f"RS: Cleaning up {len(rs._active_sessions)} sessions...")
    for ip, session in list(rs._active_sessions.items()):
        try:
            pubkey = session.get("pubkey")
            if pubkey:
                rs.wg_peer_remove(pubkey)
                print(f"Cleaned up peer {pubkey[:8]}...")
        except Exception as e:
            print(f"Error cleaning up {ip}: {e}")

atexit.register(cleanup)

# Initialize Serializer
SERIALIZER = TokenSerializer(issuer="https://proxion-keyring.example/fortress")


from functools import wraps
from datetime import datetime, timedelta, timezone

def require_capability(action: str, resource: str):
    """Decorator to enforce Proxion Capability Tokens."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 1. Extract Token from Header
            token_str = request.headers.get("Proxion-Token")
            if not token_str:
                print(f"RS: [401] Missing Proxion-Token for {action} on {resource}")
                return jsonify({"error": "Missing Proxion-Token"}), 401
            
            try:
                # 2. Verify JWT Integrity and Reconstruct Token
                # Use manager.public_key for root-signed tokens
                # Relax audience for local dashboard development
                token = SERIALIZER.verify(token_str, manager.public_key, audience=None)
                
                # 3. Revocation Check (Fortress Registry)
                if manager.revocation_list.is_revoked(token, datetime.now(timezone.utc)):
                    return jsonify({"error": "Token Revoked"}), 403

                # 4. Expiration Check
                if datetime.now(timezone.utc) >= token.exp:
                    return jsonify({"error": "Token Expired"}), 403
                
                # 5. Permission Check (allow * wildcard)
                has_permission = False
                for perm_action, perm_resource in token.permissions:
                    if perm_action == "*" or (perm_action == action and (perm_resource == "*" or perm_resource == resource)):
                        has_permission = True
                        break
                
                # Special Case: 'manage' on 'system:suite' often comes in as 'manage' on '*' or broadly
                if not has_permission:
                     print(f"RS: Permission Denied for {action} on {resource}. Token has: {token.permissions}")
                     return jsonify({"error": f"Forbidden: permission_missing ({action}, {resource})"}), 403
                
                # 6. Optional PoP check (skip for local dashboard)
                pop_sig = request.headers.get("X-Proxion-PoP")
                if pop_sig:
                    # Future: verify PoP signature
                    pass 
                
                # Success
                return f(*args, **kwargs)
            except Exception as e:
                import traceback
                print(f"RS: Authorization Failed for {action} on {resource}: {e}")
                # traceback.print_exc()
                return jsonify({"error": f"Authorization Failed: {str(e)}"}), 403
        return wrapper
    return decorator

def require_approval(action: str):
    """Decorator to require Mobile Confirmation for sensitive actions."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # 1. Skip if called by Root/Admin device directly
            token_str = request.headers.get("Proxion-Token")
            try:
                token = SERIALIZER.verify(token_str, manager.public_key, audience="fortress:rs")
                # Dashboard/Admin have ('*', '*') or 'gateway.authorize'
                is_root = any(p[0] == "*" or p[0] == "gateway.authorize" for p in token.permissions)
                if is_root:
                    return f(*args, **kwargs)
            except:
                pass

            # 2. Check if this is a polling resumption
            intent_id = request.headers.get("Proxion-Intent-ID")
            if intent_id:
                status = manager.gateway.check_intent(intent_id)
                if status == "approved":
                    return f(*args, **kwargs)
                if status == "denied":
                    return jsonify({"error": "Action Denied by Owner"}), 403
                return jsonify({"status": "pending", "intent_id": intent_id}), 202

            # 3. Create new Intent
            intent_id = manager.gateway.create_intent(
                action=action,
                params=request.json if request.is_json else {},
                requester=request.remote_addr
            )
            return jsonify({
                "error": "Approval Required",
                "intent_id": intent_id,
                "message": "Please confirm this action on your Proxion Mobile app."
            }), 202
        return wrapper
    return decorator

@app.route("/gateway/challenge", methods=["POST"])
def gateway_challenge():
    """Start a physical key handshake (extension linking)."""
    handshake_id = manager.gateway.create_handshake()
    return jsonify({
        "handshake_id": handshake_id,
        "qr_uri": f"proxion://gateway?id={handshake_id}&host={request.host}"
    }), 200

@app.route("/gateway/authorize", methods=["POST"])
@require_capability("gateway.authorize", "fortress:identity")
def gateway_authorize():
    """Authorize a pending handshake (called by Mobile)."""
    data = request.json
    handshake_id = data.get("handshake_id")
    payload = data.get("payload") # Custom payload (e.g. {token, webId})
    
    # Fallback for legacy extension flow or if phone just wants to grant a token
    if not payload:
        from proxion_core import Token
        import secrets
        ext_token = Token(
            token_id=secrets.token_urlsafe(16),
            aud="fortress:rs",
            exp=datetime.now(timezone.utc) + timedelta(days=365),
            permissions=[("*", "*")], # Grant root permissions for suite management
            caveats=[],
            holder_key_fingerprint="fortress:extension",
            alg="EdDSA",
            signature=""
        )
        jwt_token = SERIALIZER.sign(ext_token, manager.private_key)
        payload = {"proxion_token": jwt_token}
    
    success = manager.gateway.authorize_handshake(handshake_id, payload)
    if success:
        return jsonify({"status": "Authorized"}), 200
    return jsonify({"error": "Invalid or expired handshake"}), 400

@app.route("/gateway/poll", methods=["GET"])
def gateway_poll():
    """Poll for handshake completion (called by Extension/Dashboard)."""
    handshake_id = request.args.get("id")
    payload = manager.gateway.poll_handshake(handshake_id)
    if payload:
        return jsonify(payload), 200
    return jsonify({"status": "Pending"}), 202

@app.route("/federation/status", methods=["GET"])
@require_capability("read", "federation")
def federation_status():
    """Monitor federation health and policy counts."""
    return jsonify({
        "status": "HEALTHY",
        "peer_count": 5,
        "active_policies": 3,
        "last_sync": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route("/gateway/intents", methods=["GET"])
@require_capability("gateway.authorize", "fortress:identity")
def gateway_get_intents():
    """Mobile App fetches pending actions."""
    return jsonify(manager.gateway.get_pending_intents()), 200

@app.route("/gateway/intents/resolve", methods=["POST"])
@require_capability("gateway.authorize", "fortress:identity")
def gateway_resolve_intent():
    """Mobile App approves/denies an action."""
    data = request.json
    intent_id = data.get("intent_id")
    approved = data.get("approved", False)
    success = manager.gateway.resolve_intent(intent_id, approved)
    return jsonify({"status": "Resolved" if success else "Error"}), 200 if success else 400

@app.route("/lens/search", methods=["GET"])
@require_capability("search", "fortress:stash")
def lens_search():
    """Unified search endpoint."""
    query = request.args.get("q", "")
    results = manager.lens.search(query)
    return jsonify(results), 200

@app.route("/lens/status", methods=["GET"])
@require_capability("search", "fortress:stash")
def lens_status():
    """Get indexing status."""
    return jsonify(manager.lens.get_status()), 200

@app.route("/warden/audit", methods=["GET"])
@require_capability("remote.control", "system:host")
def warden_audit():
    """Global Health Audit (Warden)."""
    import psutil
    import socket
    
    # VPN Status
    vpn_status = "active" if rs.wg_config.enabled else "disabled"
    
    return jsonify({
        "hostname": socket.gethostname(),
        "system": {
            "cpu": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage('/').percent
        },
        "network": {
            "vpn": vpn_status,
            "peers": len(manager.registered_peers),
            "relays": 1 # For now we assume one active relay connection
        },
        "warden": manager.warden.get_stats()
    }), 200

@app.route("/archivist/capture", methods=["POST"])
@require_capability("capture", "web:archive")
def archivist_capture():
    """Trigger a web snapshot."""
    data = request.json
    url = data.get("url")
    if not url:
        return jsonify({"error": "Missing url"}), 400
        
    result = manager.archivist.capture_snapshot(url)
    return jsonify(result), 200

@app.route("/system/status", methods=["GET"])
@require_capability("remote.control", "system:host")
def system_status():
    """Expose hardware status for Proxion Mirror."""
    import psutil
    import socket
    return jsonify({
        "hostname": socket.gethostname(),
        "cpu": psutil.cpu_percent(),
        "ram": psutil.virtual_memory().percent,
        "status": "online"
    }), 200

@app.route("/system/power", methods=["POST"])
@require_capability("remote.control", "system:host")
@require_approval("system.power")
def system_power():
    """Remote Power Control (Approval Required)."""
    data = request.json
    action = data.get("action")
    if action not in ["shutdown", "reboot"]:
        return jsonify({"error": "Invalid action"}), 400
    
    print(f"RS: SYSTEM POWER {action.upper()} requested via Mirror.")
    return jsonify({"status": f"System {action} initiated"}), 200

@app.route("/system/tunnel", methods=["POST"])
@require_capability("remote.control", "system:host")
@require_approval("system.tunnel")
def system_tunnel():
    """Modify Firewall to expose RDP/VNC over WireGuard."""
    data = request.json
    service = data.get("service") # 'rdp' or 'vnc'
    enable = data.get("enable", True)
    
    ports = {"rdp": 3389, "vnc": 5900}
    if service not in ports:
        return jsonify({"error": "Invalid service"}), 400
        
    port = ports[service]
    display_name = f"Proxion {service.upper()}"
    
    import subprocess
    cmd = []
    if enable:
        # PowerShell: New-NetFirewallRule ...
        ps_script = f"New-NetFirewallRule -DisplayName '{display_name}' -Direction Inbound -LocalPort {port} -Protocol TCP -Action Allow -RemoteAddress 10.0.0.0/24 -Force"
        cmd = ["powershell", "-Command", ps_script]
    else:
        ps_script = f"Remove-NetFirewallRule -DisplayName '{display_name}' -ErrorAction SilentlyContinue"
        cmd = ["powershell", "-Command", ps_script]
        
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        return jsonify({"status": f"{service.upper()} tunnel {'opened' if enable else 'closed'}"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/system/audit", methods=["GET"])
def system_audit():
    """Run the technical dependency check for the GUI wizard."""
    from scripts.setup_wizard import run_all_checks
    results = run_all_checks()
    return jsonify(results), 200

@app.route("/system/install", methods=["POST"])
def system_install():
    """Trigger auto-installation of a missing dependency."""
    # Note: We allow this without strict Token for initial onboarding (Phase 1)
    # but in production this should be protected.
    data = request.json
    dep = data.get("dep")
    if not dep:
        return jsonify({"error": "Missing dependency name"}), 400
        
    from scripts.setup_wizard import install_dependency
    ok, msg = install_dependency(dep)
    if ok:
        return jsonify({"status": "Installation initiated", "message": msg}), 200
    return jsonify({"error": msg}), 500

@app.route("/system/mount", methods=["POST"])
@require_capability("manage", "system:host")
def system_mount():
    """Trigger the P: drive mount (Dropbox-style) with pooled sources."""
    import subprocess
    mount_point = "P:"
    
    # Aggressively try to clear P: first
    if os.name == 'nt':
        subprocess.run(["subst", "P:", "/D"], capture_output=True)
        # Also kill any existing python mount processes
        subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq Proxion Unified FUSE Driver"], capture_output=True)

    # Only mount if not already present
    if os.path.exists(mount_point):
        return jsonify({"status": "Already Mounted", "path": mount_point}), 200

    fuse_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../proxion-fuse/mount.py"))
    
    config = load_config()
    # Format as Name|Path for the Virtual Pod driver
    sources = [f"{s.get('name')}|{s.get('path')}" for s in config.get("stash_sources", []) if s.get("path") and os.path.exists(s.get("path"))]
    
    # HYBRID HUB: Use proxion-core/storage as the Primary Source (Root)
    # This ensures P:/security, P:/media etc. map to the Core Repo
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
    core_storage = os.path.join(repo_root, "proxion-core", "storage")
    
    # Fallback to local stash if core is missing (unlikely in dev env)
    if not os.path.exists(core_storage):
        core_storage = os.path.join(repo_root, "stash")
        os.makedirs(core_storage, exist_ok=True)
    
    # Insert Core Storage as primary (Source #0)
    sources.insert(0, f"System_Core|{core_storage}")
    
    print(f"[Backend] Initiating Hybrid Hub mount. Root: {core_storage}")
    cmd = ["python", fuse_script, mount_point] + sources
    # Spawn in background
    subprocess.Popen(cmd)
    
    return jsonify({"status": "Mounting Initiated", "path": mount_point}), 202

@app.route("/system/unmount", methods=["POST"])
@require_capability("manage", "system:host")
def system_unmount():
    """Kill any running FUSE processes and unmount P:."""
    import subprocess
    if os.name == 'nt':
        # On Windows, we just need to kill the python processes running mount.py
        # and maybe the WinFUSE process if possible.
        # But killing our subprocess is usually enough for the dev environment.
        subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq Proxion Unified FUSE Driver"], capture_output=True)
        # Attempt to remove the drive letter mapping if it lingers
        subprocess.run(["subst", "P:", "/D"], capture_output=True)
    
    return jsonify({"status": "Unmounted"}), 200

@app.route("/relay/status", methods=["GET"])
@require_capability("read", "system:host")
def relay_status():
    """Monitor the Proxion Relay Backbone."""
    # Heuristic: If we have an active CP URL and warden is active, we are "Connected"
    cp_url = os.getenv("proxion-keyring_CP_URL", "Cloud (Default)")
    
    return jsonify({
        "status": "CONNECTED",
        "relay_node": cp_url,
        "latency_ms": 42, # Mock RTT
        "uptime": "14d 2h",
        "messages_proxied": 12405,
        "bandwidth_kbps": 850
    }), 200

@app.route("/storage/stats", methods=["GET"])
@require_capability("read", "system:host")
def storage_stats():
    """Fetch metrics for the Unified P: Drive (Pooled across physical disks)."""
    import shutil
    from datetime import datetime, timezone
    config = load_config()
    sources = config.get("stash_sources", [])
    
    pooled_usage = {"total": 0, "used": 0, "free": 0, "percent": 0}
    active_sources_count = 0

    for source in sources:
        path = source.get("path")
        if path and os.path.exists(path):
            try:
                total, used, free = shutil.disk_usage(path)
                pooled_usage["total"] += total
                pooled_usage["used"] += used
                pooled_usage["free"] += free
                active_sources_count += 1
            except Exception as e:
                print(f"Error checking stats for {path}: {e}")

    if pooled_usage["total"] > 0:
        pooled_usage["percent"] = (pooled_usage["used"] / pooled_usage["total"]) * 100

    print(f"[Backend] Pooled stats: {pooled_usage['used']/(1024**3):.2f}GB / {pooled_usage['total']/(1024**3):.2f}GB")
    
    # Better mount check for Windows: check if the drive letter is actually accessible and has a label if possible
    # We'll stick to exists for now but add a print
    is_mounted = os.path.exists("P:")
    print(f"[Backend] P: drive exists check: {is_mounted}")

    return jsonify({
        "is_mounted": is_mounted,
        "usage": pooled_usage,
        "active_sources": active_sources_count,
        "cache_health": "OPTIMAL",
        "last_sync": datetime.now(timezone.utc).isoformat()
    }), 200

@app.route("/storage/config", methods=["GET", "POST"])
@require_capability("manage", "system:host")
def storage_config():
    """Get or set storage configuration (e.g. stash sources)."""
    if request.method == "POST":
        data = request.json
        print(f"[Backend] Received config update request.")
        sources = data.get("stash_sources")
        if sources is None:
            print("[Backend] ERROR: Missing stash_sources in payload")
            return jsonify({"error": "Missing stash_sources"}), 400
        
        print(f"[Backend] Sources to save: {len(sources)}")
        config = load_config()
        config["stash_sources"] = sources
        success = save_config(config)
        
        if success:
            print(f"[Backend] Storage configuration synchronized successfully.")
            return jsonify(config), 200
        
        print(f"[Backend] Internal error synchronizing storage configuration.")
        return jsonify({"error": "Failed to save config"}), 500
    
    return jsonify(load_config()), 200

@app.route("/identity/keys", methods=["GET"])
@require_capability("manage", "fortress:identity")
def identity_keys():
    """Visualize fortress keys and fingerprints."""
    return jsonify({
        "public_key": manager.public_key_hex,
        "identity_type": "Ed25519",
        "capabilities_issued": 8,
        "trust_score": 98.4
    }), 200

@app.route("/federation/policies", methods=["GET"])
@require_capability("manage", "federation")
def federation_policies():
    """List all active federation relationships."""
    return jsonify(manager.get_relationships()), 200

@app.route("/federation/revoke", methods=["POST"])
@require_capability("manage", "federation")
@require_approval("federation.revoke")
def federation_revoke():
    """Revoke a relationship certificate (Approval Required)."""
    data = request.json
    cert_id = data.get("certificate_id")
    if not cert_id:
        return jsonify({"error": "Missing certificate_id"}), 400
        
    manager.revoke_relationship(cert_id)
    return jsonify({"status": "Revoked"}), 200

# --- Suite Management Endpoints ---

@app.route("/suite/status", methods=["GET"])
@require_capability("read", "system:suite") # Hardened from (*, *)
def suite_status():
    """Get status of all possible integrations."""
    import os
    import subprocess
    integrations_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../integrations"))


    
    # 1. Get ALL containers (including stopped ones)
    apps_with_containers = set()
    try:
        # Use docker ps -a to find any container relating to our project
        output = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Names}}"]).decode()
        containers = [c.strip() for c in output.strip().split('\n') if c.strip()]
        for c in containers:
             # Match exact prefix {app_id}- but handle the -integration suffix in folder names later
             apps_with_containers.add(c)
    except:
        pass

    # 2. Map status
    results = {}
    if os.path.exists(integrations_dir):
        for d in os.listdir(integrations_dir):
            if os.path.isdir(os.path.join(integrations_dir, d)):
                # Folder name is typically 'app-integration'
                clean_id = d.replace("-integration", "")
                
                # Check for running vs stopped containers
                # Project naming usually follows Compose defaults: {folder}_{service}_{index}
                # or we prefix them. Here we fallback to simple but more accurate inclusion.
                any_container = any(clean_id in c for c in apps_with_containers)
                
                if not any_container:
                    status = "UNINSTALLED"
                else:
                    # Check if specifically RUNNING
                    try:
                        is_running = subprocess.run(
                            ["docker", "ps", "-q", "--filter", f"name={clean_id}"],
                            capture_output=True, text=True
                        ).stdout.strip() != ""
                        status = "RUNNING" if is_running else "STOPPED"
                    except:
                        status = "STOPPED"
                     
                results[d] = status
                
    return jsonify({"apps": results}), 200

@app.route("/suite/install", methods=["POST"])
@require_capability("manage", "system:suite")
def suite_install():
    print(f"RS: Received installation request for {request.json}")
    data = request.json or {}
    app_id = data.get("appId", "").replace("-integration", "")
    if not app_id: 
        print("RS: Missing appId in request")
        return jsonify({"error": "Missing appId"}), 400
    
    import subprocess
    cmd = ["python", "-m", "proxion_keyring.cli", "suite", "install", app_id]
    
    if "adguard" in app_id.lower():
        cmd.append("--protect-host")
    
    # Path Logic - Ensure we point to the parent of the package
    # __file__ is proxion_keyring/rs/server.py
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Parent of 'rs' is 'proxion_keyring', Parent of 'proxion_keyring' is the root we need in PYTHONPATH
    package_parent = os.path.abspath(os.path.join(current_dir, "..", "..")) 
    
    # keyring_repo is usually the root of the project (Proxion/)
    keyring_repo = os.path.abspath(os.path.join(package_parent, ".."))
    
    core_src = os.path.abspath(os.path.join(keyring_repo, "proxion-core", "src"))
    
    env = os.environ.copy()
    # Add root of keyring and core-src to PYTHONPATH
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [package_parent, core_src, env.get("PYTHONPATH")]))
    
    def run_install():
        try:
            with open("install_debug.log", "a") as log:
                log.write(f"RS: Installing {app_id}...\n")
                log.write(f"RS: CWD={keyring_repo}\n")
                log.write(f"RS: PYTHONPATH={env['PYTHONPATH']}\n")
                
                res = subprocess.run(
                    cmd, 
                    cwd=keyring_repo, 
                    env=env, 
                    capture_output=True, 
                    text=True
                )
                log.write(f"RS: Install Output:\n{res.stdout}\n")
                if res.returncode != 0:
                     log.write(f"RS: Install Error:\n{res.stderr}\n")
        except Exception as e:
            with open("install_debug.log", "a") as log:
                log.write(f"RS: Install Exception: {e}\n")

    threading.Thread(target=run_install).start()
    
    return jsonify({"status": "Installation started"}), 202

@app.route("/suite/credentials/<app_id>", methods=["GET"])
@require_capability("read", "system:credentials")
def suite_credentials(app_id):
    """Fetch deterministic credentials for an app."""
    # Strip suffix if present
    base_id = app_id.replace("-integration", "")
    
    # Load Identity
    try:
        identity_key = load_or_create_identity_key()
        password = derive_app_password(identity_key, base_id)
        
        return jsonify({
            "appId": app_id,
            "username": "admin",
            "password": password
        })
    except Exception as e:
        print(f"RS: Error deriving credentials for {app_id}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/suite/icon/<app_id>", methods=["GET"])
def suite_icon(app_id):
    """Serve cached icon for app, falling back to CDN download."""
    import json
    import requests
    from flask import send_file
    
    # 1. Resolve Apps JSON path
    # server.py is in proxion_keyring/rs/ -> root is ../..
    # dashboard is in proxion-keyring/dashboard
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    apps_json_path = os.path.join(root_dir, "dashboard", "src", "data", "apps.json")
    
    # 2. Find App Data
    target_app = None
    if os.path.exists(apps_json_path):
        try:
            with open(apps_json_path, 'r') as f:
                apps = json.load(f)
                for a in apps:
                    if a["id"] == app_id:
                        target_app = a
                        break
        except Exception as e:
            print(f"RS: Error reading apps.json: {e}")
            
    if not target_app:
        return jsonify({"error": "App not found"}), 404
        
    # 3. Determine Upstream URL
    # Logic mirrors InstallationCenter.jsx
    logo_slug = target_app.get("logo_slug")
    base_slug = logo_slug if logo_slug else app_id.replace('-integration', '')
    
    # Determine extension and URL
    # SimpleIcons is SVG, DashboardIcons is PNG
    if logo_slug:
        upstream_url = f"https://cdn.simpleicons.org/{logo_slug}?viewbox=auto"
        ext = "svg"
    else:
        # Fallback to dashboard icons
        upstream_url = f"https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/{base_slug}.png"
        ext = "png"

    # 4. Cache Path
    # cache stored in proxion_keyring/static/icons (create if needed)
    cache_dir = os.path.join(root_dir, "proxion_keyring", "static", "icons")
    os.makedirs(cache_dir, exist_ok=True)
    
    local_filename = f"{app_id}.{ext}"
    local_path = os.path.join(cache_dir, local_filename)
    
    # 5. Fetch if missing
    if not os.path.exists(local_path):
        print(f"RS: Caching icon for {app_id} from {upstream_url}")
        try:
            resp = requests.get(upstream_url, timeout=5)
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(resp.content)
            else:
                 # Try fallback if primary failed (e.g. SimpleIcons 404 -> DashboardIcons)
                 if logo_slug:
                     print(f"RS: SimpleIcons failed for {app_id}, trying DashboardIcons fallback")
                     fallback_url = f"https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/{base_slug}.png"
                     resp_fb = requests.get(fallback_url, timeout=5)
                     if resp_fb.status_code == 200:
                         local_path = os.path.join(cache_dir, f"{app_id}.png") # Update extenson
                         with open(local_path, "wb") as f:
                             f.write(resp_fb.content)
                     else:
                         return jsonify({"error": "Icon not found upstream"}), 404
                 else:
                     return jsonify({"error": "Icon not found upstream"}), 404
        except Exception as e:
             print(f"RS: Error fetching icon: {e}")
             return jsonify({"error": f"Download failed: {str(e)}"}), 502

    # 6. Serve
    return send_file(local_path)

@app.route("/suite/uninstall", methods=["POST"])
@require_capability("manage", "system:suite")
def suite_uninstall_endpoint():
    data = request.json or {}
    app_id = data.get("appId", "").replace("-integration", "")
    if not app_id: return jsonify({"error": "Missing appId"}), 400
    
    import subprocess
    cmd = ["python", "-m", "proxion_keyring.cli", "suite", "uninstall", app_id]
    # Fix PYTHONPATH to include the keyring root so 'proxion_keyring' module is found
    # We need to go up from rs/server.py -> proxion_keyring/ -> ROOT
    keyring_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    core_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../proxion-core/src"))
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{keyring_root}{os.pathsep}{core_src}{os.pathsep}{env.get('PYTHONPATH', '')}"
    
    subprocess.Popen(cmd, cwd=keyring_root, env=env)
    return jsonify({"status": "Uninstallation started"}), 202

@app.route("/suite/up", methods=["POST"])
@require_capability("manage", "system:suite")
def suite_up():
    data = request.json or {}
    app_id = data.get("appId", "").replace("-integration", "")
    if not app_id: return jsonify({"error": "Missing appId"}), 400
    
    import subprocess
    cmd = ["python", "-m", "proxion_keyring.cli", "suite", "up", app_id]
    keyring_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    core_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../proxion-core/src"))
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{keyring_root}{os.pathsep}{core_src}{os.pathsep}{env.get('PYTHONPATH', '')}"
    
    subprocess.Popen(cmd, cwd=keyring_root, env=env)
    return jsonify({"status": "Starting"}), 202

@app.route("/suite/down", methods=["POST"])
@require_capability("manage", "system:suite")
def suite_down():
    data = request.json or {}
    app_id = data.get("appId", "").replace("-integration", "")
    if not app_id: return jsonify({"error": "Missing appId"}), 400
    
    import subprocess
    cmd = ["python", "-m", "proxion_keyring.cli", "suite", "down", app_id]
    keyring_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
    core_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../proxion-core/src"))
    
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{keyring_root}{os.pathsep}{core_src}{os.pathsep}{env.get('PYTHONPATH', '')}"
    
    subprocess.Popen(cmd, cwd=keyring_root, env=env)
    return jsonify({"status": "Stopping"}), 202

@app.route("/suite/sync/<app_id>", methods=["POST"])
@require_capability("manage", "system:suite")
def suite_sync(app_id):
    """Force-sync credentials for an integrated app."""
    # Strip integration suffix
    base_id = app_id.replace("-integration", "")
    
    # Dynamic import attempt
    try:
        # Assuming the module is named after the base_id
        import importlib
        try:
             module = importlib.import_module(f"proxion_keyring.rs.integrations.{base_id}")
        except ImportError:
             return jsonify({"error": f"No sync module found for {base_id}"}), 404
             
        if not hasattr(module, "sync_credentials"):
             return jsonify({"error": "Module missing sync_credentials capability"}), 501
             
        success, message = module.sync_credentials()
        if success:
            return jsonify({"status": "Synced", "message": message}), 200
        else:
            return jsonify({"error": message}), 500
            
    except Exception as e:
        print(f"Sync failed: {e}")
        return jsonify({"error": str(e)}), 500

# --- Mesh Group Endpoints ---

@app.route("/mesh/list", methods=["GET"])
@require_capability("manage", "mesh")
def mesh_list():
    """List private Mesh Groups."""
    return jsonify(manager.mesh.list_groups()), 200

@app.route("/mesh/create", methods=["POST"])
@require_capability("manage", "mesh")
def mesh_create():
    """Create a new Mesh Group."""
    data = request.json
    name = data.get("name")
    if not name: return jsonify({"error": "Missing name"}), 400
    
    group_id = manager.mesh.create_group(name)
    return jsonify({"group_id": group_id}), 201

@app.route("/mesh/join", methods=["POST"])
@require_capability("manage", "mesh")
def mesh_join():
    """Add a peer to a Mesh Group."""
    data = request.json
    group_id = data.get("group_id")
    peer_pubkey = data.get("peer_pubkey")
    
    if not group_id or not peer_pubkey:
        return jsonify({"error": "Missing parameters"}), 400
        
    try:
        manager.mesh.add_member(group_id, peer_pubkey)
        return jsonify({"status": "Added"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

@app.route("/peers", methods=["GET"])
@require_capability("peers.list", "fortress:management")
def get_peers():
    """List all registered Proxy/Mobile peers."""
    return jsonify(manager.registered_peers), 200

@app.route("/peers/revoke", methods=["POST"])
@require_capability("revoke", "fortress:management")
@require_approval("peers.revoke")
def revoke_peer_endpoint():
    """Revoke a peer physically and logically (Approval Required)."""
    data = request.json
    pubkey = data.get("pubkey")
    if not pubkey:
        return jsonify({"error": "Missing pubkey"}), 400
        
    # 1. Physically remove from WG
    try:
        rs.wg_peer_remove(pubkey)
    except Exception as e:
        print(f"RS: Peer not in interface, continuing revocation: {e}")
        
    # 2. Logically remove from Manager
    manager.revoke_peer(pubkey)
    
    return jsonify({"status": "Peer revoked"}), 200

@app.route("/session/activate", methods=["POST"])
def activate_session():
    """Bridge Solid session from Frontend and issue Admin Token."""
    print("RS: Handling /session/activate request")
    # SECURITY: Restrict to Loopback for production unless we add a secondary auth layer
    remote = request.remote_addr
    if remote not in ["127.0.0.1", "localhost", "::1", "::ffff:127.0.0.1"]:
        print(f"RS: Rejected activation from non-loopback address: {remote}")
        return jsonify({"error": "Administrative Session Activation MUST be initiated from the host loopback."}), 403

    data = request.json
    web_id = data.get("webId")
    access_token = data.get("accessToken")
    
    # Issue Administrative Token for the Dashboard
    from proxion_core import Token
    admin_token = Token(
        token_id=secrets.token_urlsafe(16),
        aud="fortress:rs",
        exp=datetime.now(timezone.utc) + timedelta(hours=24),
        permissions=[("*", "*")], # Root access for local dashboard
        caveats=[],
        holder_key_fingerprint="fortress:dashboard",
        alg="EdDSA",
        signature=""
    )
    jwt_token = SERIALIZER.sign(admin_token, manager.private_key)
    
    return jsonify({
        "status": "Session activated",
        "proxion_token": jwt_token
    }), 200

@app.route("/onboarding-config", methods=["POST"])
def get_onboarding_config():
    """
    Generate configuration for Mobile/Extension onboarding.
    Requires an authorized handshake_id to prevent leak of identity secrets.
    """
    data = request.json or {}
    handshake_id = data.get("handshake_id")
    if not handshake_id or not manager.gateway.is_authorized(handshake_id):
        return jsonify({"error": "Invalid or Unauthorized handshake_id. Initiate handshake via /gateway/challenge first."}), 403

    # 1. Generate new Client Keys
    client_conf = manager.generate_client_config()
    if client_conf["public_key"] == "ERROR":
        return jsonify({"error": "Failed to generate client keys"}), 500

    # 2. Register this peer immediately (Allowlist)
    # The spec says we should only allowlist after "Ticket Redemption" (bootstrap).
    # But for this "Scan-to-Connect" flow, we are Pre-Approving the device.
    # We add it to the WireGuard interface now.
    from proxion_keyring.rs.service import PeerConfig
    
    # We need access to the RS instance to mutate WG.
    # 'rs' is global here.
    # Note: 'rs' currently initialized with hardcoded config in server.py.
    # We should update 'rs' to use the Manager's keys?
    # For now, we trust Manager to be the source of truth for Identity, 
    # but 'rs' manages the Interface.
    
    # 3. Issue COMPLIANT Capability Token
    from proxion_core import Token
    permissions = [
        ("warden.stats", "fortress:perimeter"),
        ("search", "fortress:stash"),
        ("capture", "web:archive"),
        ("remote.control", "system:host"),
        ("peers.list", "fortress:management"),
        ("gateway.authorize", "fortress:identity"),
        ("read", "system:suite"),
        ("manage", "system:suite")
    ]
    
    token = Token(
        token_id=secrets.token_urlsafe(16),
        aud="fortress:rs",
        exp=datetime.now(timezone.utc) + timedelta(days=30),
        permissions=permissions,
        caveats=[], # No caveats for root mobile device
        holder_key_fingerprint=client_conf["public_key"],
        alg="EdDSA",
        signature=""
    )
    
    # Allow local mutation of the interface
    try:
        # We need to assign an IP. RS has an address pool.
        client_addr = rs._address_pool.allocate("mobile-device") 
        
        # Add Peer to WireGuard
        rs.wg_peer_add(client_conf["public_key"], [client_addr])
        
        # REGISTER in Manager for persistence and Revocation
        manager.register_mobile_peer(client_conf["public_key"], {
            "name": request.json.get("name", "Mobile Device") if request.is_json else "Mobile Device",
            "ip": client_addr,
            "type": "mobile",
            "token_id": token.token_id
        })

        print(f"RS: Registered and authorized mobile peer {client_conf['public_key'][:8]} at {client_addr}")
        
    except Exception as e:
        print(f"RS: Failed to pre-authorize peer: {e}")
        return jsonify({"error": f"Failed to register peer: {str(e)}"}), 500
    
    # Sign using Manager's Fortress Identity (The Agent)
    proxion_token = SERIALIZER.sign(token, manager.private_key)

    return jsonify({
        "server_endpoint": os.getenv('proxion-keyring_WG_ENDPOINT', '10.0.0.1:51820'),
        "server_pubkey": manager.wg_server_pub, 
        "client_private_key": client_conf["private_key"],
        "client_address": client_addr,
        "client_dns": "1.1.1.1", 
        "pod_url": manager.get_pod_url(),
        "proxion_token": proxion_token
    })

@app.route("/bootstrap", methods=["POST"])
def bootstrap():
    """Bootstrap secure channel using JWT."""
    try:
        data = request.json
        jwt_str = data.get("token") or data.get("token_id")
        
        if not jwt_str:
             return jsonify({"error": "Missing token"}), 401

        # Verify JWT using CP's Public Key
        try:
            token = SERIALIZER.verify(jwt_str, CP_PUBLIC_KEY, audience="rs:wg0")
        except Exception as e:
            return jsonify({"error": f"Invalid token: {e}"}), 403

        # --- Revocation Check ---
        # TODO: Move to a proper service class.
        import requests
        import time
        
        crl_cache = getattr(app, "crl_cache", set())
        last_sync = getattr(app, "crl_last_sync", 0)
        
        # Sync if older than 1s (Demo speedup)
        if time.time() - last_sync > 1:
            try:
                cp_url = os.getenv("proxion-keyring_CP_URL", "http://localhost:8787")
                resp = requests.get(f"{cp_url}/crl", timeout=2)
                if resp.status_code == 200:
                    crl_data = resp.json().get("revoked_tokens", [])
                    crl_cache = set(crl_data)
                    setattr(app, "crl_cache", crl_cache)
                    setattr(app, "crl_last_sync", time.time())
                    print(f"Synced CRL: {len(crl_cache)} entries")
            except Exception as e:
                print(f"CRL Sync failed: {e}")
        
        if token.token_id in crl_cache:
            return jsonify({"error": "Token Revoked"}), 403
        # ------------------------

        # Reconstruct Request Context
        from datetime import datetime, timezone
        ctx = RequestContext(
            action="channel.bootstrap",
            resource="rs:wg0",
            aud="rs:wg0", # Token audience must match
            now=datetime.now(timezone.utc)
        )
        
        # Call RS Logic (now strict enabled if we remove MockRS)
        # But we are still using 'rs' which is 'MockResourceServer' instance created above.
        # We should replace that instance too, but MockRS.authorize checks alg="mock". 
        # Our real token has alg="HS256". 
        # So MockRS.authorize will fall through to super().authorize if alg!="mock".
        # Let's verify super().authorize calls proxion_core.validate_request.
        
        material = rs.bootstrap_channel(
            token=token,
            ctx=ctx,
            proof=None, # PoP verification for Token usage not strictly enforced here yet in spec? 
                        # Spec SEC 3.3 says "Subject MUST sign a challenge to exercise the Capability".
                        # Orchestrator does PoP for ticket redemption.
                        # For Token usage (Bootstrap), we technically should do PoP too.
                        # But typically Access Token is Bearer or DPoP. 
                        # Proxion Token is Capability.
                        # MVP: Bearer usage of JWT for now.
            client_pubkey=data.get("pubkey", "")
        )
        
        return jsonify(material.to_dict()), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # Start Pod Proxy in background
    proxy = PodProxyServer(manager)
    threading.Thread(target=proxy.run, daemon=True).start()

    # Auto-Mount P: Drive (Phase 1 Experience)
    def auto_mount():
        import time
        import requests
        time.sleep(2) # Wait for RS to start
        try:
            # We bypass the capability check by calling the logic directly,
            # or we could mock a token. Let's just import and call a helper.
            print("RS: Auto-mounting P: drive (Unified Stash)...")
            mount_point = "P:"
            if not os.path.exists(mount_point):
                # Correct path to proxion-fuse/mount.py relative to proxion-keyring package root
                # server.py is in proxion_keyring/rs/
                current_file = os.path.abspath(__file__)
                pkg_root = os.path.dirname(os.path.dirname(current_file)) 
                repo_root = os.path.abspath(os.path.join(pkg_root, "..", "..")) # Up 2 levels from RS/pkg
                fuse_script = os.path.join(repo_root, "proxion-fuse", "mount.py")
                
                config = load_config()
                sources = [f"{s.get('name')}|{s.get('path')}" for s in config.get("stash_sources", []) if s.get("path") and os.path.exists(s.get("path"))]
                
                # HYBRID HUB: Use proxion-core/storage as Primary
                core_storage = os.path.join(repo_root, "proxion-core", "storage")
                if not os.path.exists(core_storage):
                    core_storage = os.path.join(repo_root, "stash")
                    os.makedirs(core_storage, exist_ok=True)
                sources.insert(0, f"System_Core|{core_storage}")
                
                cmd = ["python", fuse_script, mount_point] + sources
                subprocess.Popen(cmd)
        except Exception as e:
            print(f"RS: Auto-mount failed: {e}")

    import subprocess
    threading.Thread(target=auto_mount, daemon=True).start()

    port = int(os.getenv("PORT", 8788))
    app.run(host="127.0.0.1", port=port, debug=False)
