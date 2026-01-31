"""Kleitikon Identity Gateway (Phase 7).

Acts as an authorized proxy for Antigravity (Port 3000).
Checks incoming IP against active Kleitikon sessions.
"""

import os
import requests
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# Config
ANTIGRAVITY_URL = os.getenv("ANTIGRAVITY_URL", "http://localhost:3000")
RS_URL = os.getenv("KLEITIKON_RS_URL", "http://localhost:8788")

def is_authorized(ip: str) -> bool:
    """Check if the source IP has an active Kleitikon session."""
    try:
        # Query Resource Server for active sessions
        resp = requests.get(f"{RS_URL}/sessions", timeout=1)
        if resp.status_code == 200:
            sessions = resp.json()
            print(f"Gateway: Checking IP {ip} against sessions: {list(sessions.keys())}")
            return ip in sessions
        else:
            print(f"Gateway: RS sessions returned {resp.status_code}")
    except Exception as e:
        print(f"Gateway: Auth check failed: {e}")
    return False

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def proxy(path):
    """Proxy requests to Antigravity IF authorized."""
    source_ip = request.remote_addr
    
    # In a real WireGuard setup, the packets come from the tunnel IP.
    # For local dev/demo, we might need a bypass or specific header.
    if os.getenv("KLEITIKON_DEV_MODE") == "1" and request.headers.get("X-Kleitikon-Sim-IP"):
         source_ip = request.headers.get("X-Kleitikon-Sim-IP")

    if not is_authorized(source_ip):
         return jsonify({
             "error": "Unauthorized Access",
             "message": f"Kleitikon session at {source_ip} not found. Please bootstrap your tunnel.",
             "proxion_spec": "Sec 8 (Authorization Logic Failure)"
         }), 403

    # Forward request to Antigravity
    url = f"{ANTIGRAVITY_URL}/{path}"
    print(f"Gateway: Forwarding {request.method} {url} for {source_ip}")
    
    try:
        # Simple proxying (Method/Body/Headers)
        resp = requests.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers if k.lower() != 'host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=5
        )
        
        # Exclude hop-by-hop headers
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        return Response(resp.content, resp.status_code, headers)
    except Exception as e:
        return jsonify({"error": f"Failed to forward to Antigravity: {e}"}), 502

if __name__ == "__main__":
    port = int(os.getenv("GATEWAY_PORT", 3001))
    print(f"--- Kleitikon Identity Gateway ---")
    print(f"Proxying {ANTIGRAVITY_URL} via port {port}")
    app.run(host="127.0.0.1", port=port, debug=False)
