"""proxion-keyring Identity Gateway (Phase 7).

Acts as an authorized proxy for Antigravity (Port 3000).
Checks incoming IP against active proxion-keyring sessions.
"""

import os
import json
import requests
import time
from flask import Flask, request, jsonify, Response

# Federation Imports
try:
    from proxion_core.federation import RelationshipCertificate
except ImportError:
    RelationshipCertificate = None

app = Flask(__name__)

# Config
ANTIGRAVITY_URL = os.getenv("ANTIGRAVITY_URL", "http://localhost:3000")
ANTIGRAVITY_TOKEN = os.getenv("ANTIGRAVITY_TOKEN")
ANTIGRAVITY_TOKEN_FILE = os.getenv("ANTIGRAVITY_TOKEN_FILE")
RS_URL = os.getenv("proxion-keyring_RS_URL", "http://localhost:8788")
DEV_MODE = os.getenv("proxion-keyring_DEV_MODE") == "1"
SESSION_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'stash', 'vault', 'sessions.json')
RELATIONSHIP_REGISTRY_PATH = os.path.join(os.path.dirname(__file__), '..', 'stash', 'vault', 'relationships.json')


def is_loopback(ip: str) -> bool:
    return ip in ["127.0.0.1", "localhost", "::1", "::ffff:127.0.0.1"]


def _read_token_file(path: str | None) -> str | None:
    if not path:
        return None
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                token = f.read().strip()
                return token or None
        except Exception as e:
            print(f"Gateway: Error reading token file {path}: {e}")
    return None

def is_authorized(ip: str, relationship_token: Optional[str] = None) -> bool:
    """Check if the source IP or relationship token is authorized."""
    if DEV_MODE and is_loopback(ip):
        print("Gateway: DEV_MODE loopback bypass enabled")
        return True

    # Check for federated relationship certificate
    if relationship_token:
        try:
            # Load relationships to check if this token exists and is valid
            if os.path.exists(RELATIONSHIP_REGISTRY_PATH):
                with open(RELATIONSHIP_REGISTRY_PATH, "r") as f:
                    registry = json.load(f)
                    # For Phase 2, we expect the token to be a Certificate ID or the full cert JSON
                    if relationship_token in registry:
                        cert = registry[relationship_token]
                        if cert.get("expires_at", 0) > time.time():
                             return True
        except Exception as e:
            print(f"Gateway: Relationship validation failed: {e}")

    try:
        # Query Resource Server for active sessions
        resp = requests.get(f"{RS_URL}/sessions", timeout=1)
        if resp.status_code == 200:
            sessions = resp.json()
            return ip in sessions
    except Exception as e:
        print(f"Gateway: Auth check failed: {e}")
    return False

def get_antigravity_config():
    """Discover Antigravity port and token via magic file."""
    magic_path = "P:/.antigravity"
    url = ANTIGRAVITY_URL
    token = ANTIGRAVITY_TOKEN or _read_token_file(ANTIGRAVITY_TOKEN_FILE)
    
    if os.path.exists(magic_path):
        try:
            with open(magic_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                token = config.get('token') or token

                if isinstance(config.get("url"), str) and config.get("url"):
                    url = config["url"]
                else:
                    scheme = config.get("scheme") or os.getenv("ANTIGRAVITY_SCHEME", "http")
                    host = config.get("host") or os.getenv("ANTIGRAVITY_HOST", "localhost")
                    port = config.get("port", 3000)
                    url = f"{scheme}://{host}:{port}"

                print(f"Gateway: Discovered Antigravity at {url} (token found: {bool(token)})")
        except Exception as e:
            print(f"Gateway: Error reading magic file: {e}")
    return url, token

def _forward_request(url, headers):
    """Forward request to Antigravity with protocol fallback."""
    verify_tls = os.getenv("ANTIGRAVITY_TLS_INSECURE") != "1"
    try:
        return requests.request(
            method=request.method,
            url=url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=5,
            verify=verify_tls,
        )
    except requests.exceptions.ConnectionError as e:
        if url.startswith("http://"):
            https_url = "https://" + url[len("http://"):]
            print(f"Gateway: HTTP failed, retrying via HTTPS -> {https_url}")
            return requests.request(
                method=request.method,
                url=https_url,
                headers=headers,
                data=request.get_data(),
                cookies=request.cookies,
                allow_redirects=False,
                timeout=5,
                verify=verify_tls,
            )
        raise e

@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def proxy(path):
    """Proxy requests to Antigravity IF authorized."""
    source_ip = request.remote_addr
    relationship_token = request.headers.get("X-Proxion-Relationship-Token")
    
    if DEV_MODE and request.headers.get("X-proxion-keyring-Sim-IP"):
         source_ip = request.headers.get("X-proxion-keyring-Sim-IP")

    if not is_authorized(source_ip, relationship_token):
         return jsonify({
             "error": "Unauthorized Access",
             "message": f"proxion-keyring session at {source_ip} not found. Please bootstrap your tunnel.",
             "proxion_spec": "Sec 8 (Authorization Logic Failure)"
         }), 403

    # Register session for FUSE enforcement (PID based)
    if relationship_token:
        _register_gateway_session(relationship_token)

    # Discover current config
    url_base, token = get_antigravity_config()
    url = f"{url_base}/{path}"
    
    # Prepare headers
    headers = {k: v for k, v in request.headers if k.lower() != 'host'}
    if token:
        headers["Authorization"] = f"Bearer {token}"
        
    print(f"Gateway: Forwarding {request.method} {url} for {source_ip}")
    
    try:
        # Simple proxying (Method/Body/Headers)
        resp = _forward_request(url, headers)

        # Fallback: Antigravity sometimes has no snapshot yet even though DOM is reachable.
        if resp.status_code == 503 and path.strip("/").startswith("snapshot"):
            try:
                probe_url = f"{url_base}/debug/upload-probe"
                probe_resp = _forward_request(probe_url, headers)
                if probe_resp.status_code == 200:
                    probe = probe_resp.json()
                    contexts = []
                    for target in probe.get("targets", []):
                        contexts.extend(target.get("contexts", []))
                    context_html = None
                    for ctx in contexts:
                        data = ctx.get("data") or {}
                        if data.get("contextHtml"):
                            context_html = data["contextHtml"]
                            break
                    if context_html:
                        snapshot = {
                            "html": context_html,
                            "controlsHtml": context_html,
                            "css": "",
                            "backgroundColor": "#1a1e26",
                            "color": "#eceff4",
                            "fontFamily": "system-ui, sans-serif",
                            "themeClass": "",
                            "themeAttr": "",
                            "colorScheme": "dark",
                            "bodyBg": "#1a1e26",
                            "bodyColor": "#eceff4"
                        }
                        return Response(json.dumps(snapshot), 200, {"Content-Type": "application/json"})
            except Exception as e:
                print(f"Gateway: Snapshot fallback failed: {e}")

        # Inject WebSocket rewrite for gateway HTML/JS so WS connects directly to Antigravity server.
        content_type = resp.headers.get("content-type", "")
        if resp.status_code == 200 and (
            "text/html" in content_type.lower()
            or "application/javascript" in content_type.lower()
            or "text/javascript" in content_type.lower()
        ):
            try:
                ws_scheme = "wss" if url_base.lower().startswith("https://") else "ws"
                host = request.host.split(":")[0]
                ws_origin = f"{ws_scheme}://{host}:3000"
                inject = (
                    "<script>(function(){"
                    f"const wsOrigin='{ws_origin}';"
                    "const OrigWS=window.WebSocket;"
                    "window.WebSocket=function(url,protocols){"
                    "try{const u=new URL(url,window.location.href);"
                    "if(u.host===window.location.host){"
                    "return new OrigWS(wsOrigin+u.pathname+u.search,protocols);"
                    "}}catch(e){}"
                    "return new OrigWS(url,protocols);"
                    "};"
                    "window.WebSocket.prototype=OrigWS.prototype;"
                    "})();</script>"
                )
                text = resp.text
                # If JS, do a simple literal rewrite too
                text = text.replace("ws://", f"{ws_scheme}://").replace(":3001", ":3000")
                if "text/html" in content_type.lower():
                    if "</head>" in text:
                        text = text.replace("</head>", inject + "</head>", 1)
                    else:
                        text = inject + text
                return Response(text, 200, {"Content-Type": content_type})
            except Exception as e:
                print(f"Gateway: WS inject failed: {e}")
        
        # Exclude hop-by-hop headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers_to_return = [(name, value) for (name, value) in resp.raw.headers.items()
                             if name.lower() not in excluded_headers]

        return Response(resp.content, resp.status_code, headers_to_return)
    except Exception as e:
        return jsonify({"error": f"Failed to forward to Antigravity: {e}"}), 502

def _register_gateway_session(relationship_token: str):
    """Register the current gateway process as an authorized session for the peer."""
    try:
        if os.path.exists(RELATIONSHIP_REGISTRY_PATH):
            with open(RELATIONSHIP_REGISTRY_PATH, "r") as f:
                registry = json.load(f)
                cert = registry.get(relationship_token)
                if cert:
                    peer_pubkey = cert.get("subject")
                    session_data = {}
                    if os.path.exists(SESSION_REGISTRY_PATH):
                        with open(SESSION_REGISTRY_PATH, "r") as sf:
                            session_data = json.load(sf)
                    
                    session_data[str(os.getpid())] = peer_pubkey
                    
                    os.makedirs(os.path.dirname(SESSION_REGISTRY_PATH), exist_ok=True)
                    with open(SESSION_REGISTRY_PATH, "w") as sf:
                        json.dump(session_data, sf)
    except Exception as e:
        print(f"Gateway: Session registration failed: {e}")

@app.route("/_gateway/status", methods=["GET"])
def gateway_status():
    """Lightweight status for debugging gateway config."""
    url_base, token = get_antigravity_config()
    return jsonify({
        "antigravity_url": url_base,
        "token_present": bool(token),
        "dev_mode": DEV_MODE,
    }), 200

if __name__ == "__main__":
    port = int(os.getenv("GATEWAY_PORT", 3001))
    host = os.getenv("GATEWAY_HOST", "127.0.0.1")
    print(f"--- proxion-keyring Identity Gateway ---")
    print(f"Proxying {ANTIGRAVITY_URL} via port {port}")
    app.run(host=host, port=port, debug=False)
