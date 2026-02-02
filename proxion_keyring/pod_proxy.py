from flask import Flask, request, Response, jsonify
import requests
from .manager import KeyringManager

class PodProxyServer:
    """
    HTTP Proxy (localhost:8089) that attaches Solid Auth and routes via Tunnels.
    Spec Compliant: Uses the Manager for all auth/routing decisions.
    """
    
    def __init__(self, manager: KeyringManager):
        self.manager = manager
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/pod/<path:pod_path>', methods=['GET', 'PUT', 'POST'])
        def handle_pod_request(pod_path):
            """Proxy request to the user's Solid Pod with auth headers."""
            pod_url = self.manager.get_pod_url()
            full_url = f"{pod_url}/{pod_path}"
            
            # 1. Check for Hybrid Routing (Metadata Index)
            if 'movie' in pod_path.lower():
                return self._route_through_tunnel(pod_path)

            # 2. Local Filesystem Override (Win32 Path Detection)
            # If the path looks like 'c:/Users/...', serve locally
            import os
            # Normalize path for check (simple valid drive letter check)
            if len(pod_path) > 1 and pod_path[1] == ':' or pod_path.startswith('/') and len(pod_path) > 2 and pod_path[2] == ':':
                 local_path = pod_path
                 if local_path.startswith('/'): local_path = local_path[1:] # strip leading / if present
                 
                 try:
                     if request.method == 'GET':
                         if os.path.isdir(local_path):
                             # Minimal LDP Container Turtle
                             return "@prefix ldp: <http://www.w3.org/ns/ldp#>.\n@prefix dcterms: <http://purl.org/dc/terms/>.\n<> a ldp:BasicContainer, ldp:Container.", 200, {'Content-Type': 'text/turtle'}
                         elif os.path.exists(local_path):
                             def generate():
                                 with open(local_path, "rb") as f:
                                     while chunk := f.read(1024*64): yield chunk
                             return Response(generate(), mimetype="application/octet-stream")
                         else:
                             return jsonify({"error": "Not Found"}), 404
                             
                     elif request.method == 'PUT':
                         # specific check for directory creation via Link header or just if path ends in /
                         is_dir_req = local_path.endswith('/') or local_path.endswith('\\')
                         
                         if is_dir_req:
                             if os.path.isdir(local_path):
                                 return "", 200
                             os.makedirs(local_path, exist_ok=True)
                             return "", 201
                         
                         # File write
                         parent = os.path.dirname(local_path)
                         if not os.path.exists(parent):
                             os.makedirs(parent, exist_ok=True)
                             
                         with open(local_path, "wb") as f:
                             f.write(request.get_data())
                         return "", 201
                         
                     elif request.method == 'DELETE':
                         if os.path.isdir(local_path):
                             os.rmdir(local_path)
                         elif os.path.exists(local_path):
                             os.remove(local_path)
                         return "", 204
                         
                     return jsonify({"error": "Method Not Allowed"}), 405
                 except Exception as e:
                     return jsonify({"error": str(e)}), 500

            # 3. Standard Pod Proxy (Remote)
            auth_headers = self.manager.get_auth_headers(full_url, request.method)
            
            # Forward relevant client headers (Accept, Range, etc.)
            client_headers = {k: v for k, v in request.headers if k.lower() in ['accept', 'range', 'content-type']}
            client_headers.update(auth_headers)
            
            try:
                resp = requests.request(
                    method=request.method,
                    url=full_url,
                    headers=client_headers,
                    data=request.get_data(),
                    stream=True if request.method == 'GET' else False
                )
                
                # Stream binary content back (photos/music)
                return Response(
                    resp.iter_content(chunk_size=1024*64),
                    status=resp.status_code,
                    headers=dict(resp.headers)
                )
            except Exception as e:
                return jsonify({"error": f"Pod fetch failed: {str(e)}"}), 502

    def _route_through_tunnel(self, path: str):
        """Redirect or Proxy through WireGuard Tunnel."""
        # Logic: Find which tunnel has this file
        tunnel_id = "home-server-main" # Hardcoded for now
        peer_ip = self.manager.get_tunnel_ip(tunnel_id)
        
        if not peer_ip:
            return jsonify({"error": f"Tunnel {tunnel_id} not established"}), 503
            
        tunnel_url = f"http://{peer_ip}/storage/{path}"
        
        try:
            resp = requests.get(tunnel_url, stream=True)
            return Response(
                resp.iter_content(chunk_size=1024*64),
                status=resp.status_code,
                headers=dict(resp.headers)
            )
        except Exception as e:
            return jsonify({"error": f"Tunnel streaming failed: {str(e)}"}), 504

    def run(self, port=8089):
        print(f"Pod Proxy running on http://localhost:{port}")
        self.app.run(host='127.0.0.1', port=port, debug=False)
