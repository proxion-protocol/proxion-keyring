import os
import errno
from flask import Flask, request, Response, jsonify
import requests
from .manager import KeyringManager
from typing import List, Dict, Optional, Any

class BaseResourceProvider:
    """Interface for Solid Resource Providers (Local, Remote, Virtual)."""
    def get_attr(self, path: str) -> Optional[Dict[str, Any]]: ...
    def list_dir(self, path: str) -> List[str]: ...
    def read_stream(self, path: str): ...
    def write(self, path: str, data: bytes, offset: int = 0) -> bool: ...
    def create(self, path: str, is_dir: bool = False) -> bool: ...
    def delete(self, path: str) -> bool: ...

class LocalProvider(BaseResourceProvider):
    """MANAGES ACCESS to the physical POD_LOCAL_ROOT."""
    EXCLUSION_LIST = {
        'identity_private.pem', '.pem', '.git', '.DS_Store', 
        'Thumbs.db', 'proxion_config.json', 'warden_blocklist.txt'
    }
    HIDDEN_LIST = {'.acl', '.meta'}

    def __init__(self, root_path: str):
        self.root_path = os.path.abspath(root_path)

    def _safe_path(self, pod_path: str) -> str:
        """Translates pod path to safe local path, preventing traversal."""
        safe_path = os.path.abspath(os.path.join(self.root_path, pod_path.lstrip('/\\')))
        if not safe_path.startswith(self.root_path):
            raise PermissionError("Path traversal escape attempted")
        
        # Check Exclusion List
        basename = os.path.basename(safe_path)
        if basename in self.EXCLUSION_LIST or any(basename.endswith(ext) for ext in self.EXCLUSION_LIST if ext.startswith('.')):
            raise PermissionError(f"Access to {basename} is restricted for safety")
            
        return safe_path

    def get_attr(self, pod_path: str):
        path = self._safe_path(pod_path)
        if not os.path.exists(path): return None
        st = os.stat(path)
        return {
            "st_mode": st.st_mode,
            "st_nlink": st.st_nlink,
            "st_size": st.st_size,
            "st_ctime": st.st_ctime,
            "st_mtime": st.st_mtime,
            "st_atime": st.st_atime,
            "proxion_status": "synced"
        }

    def list_dir(self, pod_path: str):
        path = self._safe_path(pod_path)
        if not os.path.isdir(path): return []
        entries = os.listdir(path)
        # Filter exclusions and hidden sidecars
        return [
            e for e in entries 
            if e not in self.EXCLUSION_LIST 
            and not any(e.endswith(ext) for ext in self.HIDDEN_LIST)
            and not any(e.endswith(ext) for ext in self.EXCLUSION_LIST if ext.startswith('.'))
        ]

    def read_stream(self, pod_path: str):
        path = self._safe_path(pod_path)
        def generate():
            with open(path, "rb") as f:
                while chunk := f.read(1024*64): yield chunk
        return generate()

    def write(self, pod_path: str, data: bytes, offset: int = 0):
        path = self._safe_path(pod_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = 'r+b' if os.path.exists(path) else 'wb'
        with open(path, mode) as f:
            f.seek(offset)
            f.write(data)
        return True

    def create(self, pod_path: str, is_dir: bool = False):
        path = self._safe_path(pod_path)
        if is_dir:
            os.makedirs(path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, 'wb').close()
        return True

    def delete(self, pod_path: str):
        path = self._safe_path(pod_path)
        if os.path.isdir(path):
            os.rmdir(path)
        else:
            os.remove(path)
            # Solid Cleanup Axiom: Purge sidecars
            self._cleanup_sidecars(path)
        return True

    def _cleanup_sidecars(self, path: str):
        """Purge .acl and .meta files associated with a resource."""
        for ext in self.HIDDEN_LIST:
            sidecar = path + ext
            if os.path.exists(sidecar):
                try:
                    os.remove(sidecar)
                except:
                    pass

class RemoteProvider(BaseResourceProvider):
    """MOCK Provider for demonstrating Hybrid Hub (Remote Solid Resources)."""
    def __init__(self, name: str):
        self.name = name

    def get_attr(self, path: str):
        # Return a mock directory for discovery
        if not path or path == "/":
            return {"st_mode": 0o40755, "st_size": 0, "st_mtime": 0, "proxion_status": "synced"}
        if "cloud_data.txt" in path:
            return {"st_mode": 0o100644, "st_size": 1024, "st_mtime": 0, "proxion_status": "cloud-only"}
        return None

    def list_dir(self, path: str):
        return ["cloud_data.txt"] if not path or path == "/" else []

    def read_stream(self, path: str):
        yield b"This is a virtual remote resource from " + self.name.encode()

class HybridHub(BaseResourceProvider):
    """Multiplexes between Local and Remote providers based on path prefixes."""
    def __init__(self):
        self.mounts: Dict[str, BaseResourceProvider] = {}
        self._root_entries = []

    def mount(self, prefix: str, provider: BaseResourceProvider):
        prefix = prefix.strip('/')
        self.mounts[prefix] = provider
        if prefix not in self._root_entries:
            self._root_entries.append(prefix)

    def _route(self, path: str):
        path = path.lstrip('/')
        for prefix, provider in self.mounts.items():
            if path == prefix:
                return provider, ""
            if path.startswith(prefix + "/"):
                return provider, path[len(prefix)+1:]
        return None, path

    def get_attr(self, path: str):
        if not path or path == "/" or path == ".":
            return {"st_mode": 0o40755, "st_size": 0, "st_mtime": 0}
        provider, subpath = self._route(path)
        if provider: return provider.get_attr(subpath)
        return None

    def list_dir(self, path: str):
        if not path or path == "/" or path == ".":
            return self._root_entries
        provider, subpath = self._route(path)
        if provider: return provider.list_dir(subpath)
        return []

    def read_stream(self, path: str):
        provider, subpath = self._route(path)
        if provider: return provider.read_stream(subpath)
        raise FileNotFoundError()

    def write(self, path: str, data: bytes, offset: int = 0):
        provider, subpath = self._route(path)
        if provider: return provider.write(subpath, data, offset)
        return False

    def create(self, path: str, is_dir: bool = False):
        provider, subpath = self._route(path)
        if provider: return provider.create(subpath, is_dir)
        return False

    def delete(self, path: str):
        provider, subpath = self._route(path)
        if provider: return provider.delete(subpath)
        return False

# WebDAV Integration
from wsgidav.dav_provider import DAVProvider, DAVCollection, DAVNonCollection
from wsgidav import util
import io

class GeneratorStream:
    """Wraps a generator to provide a file-like read() method."""
    def __init__(self, gen):
        self.gen = gen
        self.buf = b""

    def read(self, size=-1):
        if size == -1:
            return self.buf + b"".join(self.gen)
        
        while len(self.buf) < size:
            try:
                self.buf += next(self.gen)
            except StopIteration:
                break
        
        res = self.buf[:size]
        self.buf = self.buf[size:]
        return res

    def close(self):
        pass

class ProxionResource(DAVNonCollection):
    def __init__(self, path, environ, hub):
        super().__init__(path, environ)
        self.hub = hub
        self.attr = hub.get_attr(path) or {}

    def get_content_length(self):
        return self.attr.get("st_size", 0)

    def get_content_type(self):
        return "application/octet-stream"

    def get_creation_date(self):
        return self.attr.get("st_ctime", 0)

    def get_last_modified(self):
        return self.attr.get("st_mtime", 0)

    def get_content(self):
        return GeneratorStream(self.hub.read_stream(self.path))

    def get_etag(self):
        return f"{self.attr.get('st_mtime', 0)}-{self.attr.get('st_size', 0)}"

    def support_etag(self):
        return True

    def support_content_length(self):
        return True

    def support_modified(self):
        return True

class ProxionCollection(DAVCollection):
    def __init__(self, path, environ, hub):
        super().__init__(path, environ)
        self.hub = hub

    def get_member_names(self):
        return self.hub.list_dir(self.path)

    def get_member(self, name):
        path = os.path.join(self.path, name).replace("\\", "/")
        attr = self.hub.get_attr(path)
        if not attr: return None
        if bool(attr['st_mode'] & 0o40000):
            return ProxionCollection(path, self.environ, self.hub)
        return ProxionResource(path, self.environ, self.hub)

    def get_creation_date(self):
        attr = self.hub.get_attr(self.path) or {}
        return attr.get("st_ctime", 0)

    def get_last_modified(self):
        attr = self.hub.get_attr(self.path) or {}
        return attr.get("st_mtime", 0)

    def support_etag(self):
        return False

class ProxionDAVProvider(DAVProvider):
    def __init__(self, hub):
        super().__init__()
        self.hub = hub

    def get_resource_inst(self, path, environ):
        # path is already normalized in WsgiDAV 4.x
        attr = self.hub.get_attr(path)
        if not attr: return None
        if bool(attr['st_mode'] & 0o40000):
            return ProxionCollection(path, environ, self.hub)
        return ProxionResource(path, environ, self.hub)

class PodProxyServer:
    """
    HTTP Proxy (localhost:8089) that attaches Solid Auth and routes via HybridHub.
    """
    
    def __init__(self, manager: KeyringManager):
        self.manager = manager
        self.manager.pod_proxy = self  # Register for Lens discovery
        # Initialize Hybrid Hub
        self.hub = HybridHub()
        self.hub.mount("stash", LocalProvider(self.manager.pod_local_root))
        self.hub.mount("cloud", RemoteProvider("Mullvad-Solid-Bunker"))
        
        self.app = Flask(__name__)
        self._setup_routes()

        # Setup WebDAV
        from wsgidav.wsgidav_app import WsgiDAVApp
        config = {
            "host": "0.0.0.0",
            "port": 8089,
            "provider_mapping": {"/": ProxionDAVProvider(self.hub)},
            "simple_dc": {"user_mapping": {"*": True}}, # Anonymous for local bridge
            "verbose": 1,
        }
        self.dav_app = WsgiDAVApp(config)

        # Dispatcher
        from werkzeug.middleware.dispatcher import DispatcherMiddleware
        self.combined_app = DispatcherMiddleware(self.app, {
            "/dav": self.dav_app
        })

    def _setup_routes(self):

        @self.app.route('/auth/stash_login', methods=['POST'])
        def stash_login():
            hostname = request.headers.get('Host', '')
            if 'localhost' not in hostname and '127.0.0.1' not in hostname:
                return jsonify({"error": "Unauthorized: Localhost only"}), 403
            
            data = request.json
            if not data or "pubkey" not in data:
                return jsonify({"error": "Missing pubkey"}), 400
            
            token = self.manager.mint_stash_token(data["pubkey"])
            return jsonify(token)

        @self.app.route('/pod/search', methods=['GET'])
        def handle_search():
            query = request.args.get('q', '')
            if not query:
                return jsonify([])
            
            # Use Lens for search
            results = self.manager.lens.search(query)
            return jsonify(results)

        @self.app.route('/pod/', defaults={'pod_path': ''}, methods=['GET', 'PUT', 'POST', 'DELETE'])
        @self.app.route('/pod/<path:pod_path>', methods=['GET', 'PUT', 'POST', 'DELETE'])
        def handle_pod_request(pod_path):
            """Proxy request to Hybrid Hub (Local or Remote)."""
            # 1. CAPABILITY ENFORCEMENT
            auth_header = request.headers.get("Authorization")
            dpop_header = request.headers.get("DPoP")

            if not auth_header or not auth_header.startswith("Bearer "):
                 return jsonify({"error": "Missing or invalid Authorization header"}), 401
            if not dpop_header:
                 return jsonify({"error": "Missing DPoP proof of possession"}), 401
            
            token_json = auth_header.split(" ", 1)[1]
            try:
                import json
                proof = json.loads(dpop_header)
            except:
                return jsonify({"error": "Malformed DPoP proof"}), 400

            method_map = {"GET": "READ", "PUT": "WRITE", "POST": "CREATE", "DELETE": "DELETE"}
            ctx_data = {
                "action": method_map.get(request.method, "READ"),
                "resource": "/" + pod_path.lstrip('/')
            }

            decision = self.manager.validate_token(token_json, ctx_data, proof)
            if not decision.allowed:
                return jsonify({"error": f"Unauthorized: {decision.reason}"}), 403

            # 2. HYBRID HUB ROUTING
            try:
                # 2.1 Virtual Sidecar Handling (.status)
                if pod_path.endswith(".status"):
                    real_path = pod_path[:-7]
                    attr = self.hub.get_attr(real_path)
                    if attr:
                        status = attr.get("proxion_status", "unknown")
                        return Response(status, mimetype="text/plain")

                if request.method == 'GET':
                    attr = self.hub.get_attr(pod_path)
                    if attr:
                        # Discovery Headers
                        base_name = os.path.basename(pod_path.rstrip('/'))
                        if not base_name: base_name = "."
                        links = [
                            f'<{base_name}.acl>; rel="acl"',
                            f'<{base_name}.meta>; rel="describedby"'
                        ]
                        is_dir = bool(attr['st_mode'] & 0o40000)
                        if is_dir:
                             links.append('<http://www.w3.org/ns/ldp#BasicContainer>; rel="type"')
                        
                        resp_headers = {"Link": ", ".join(links)}
                        accept = request.headers.get('Accept', '')

                        if 'text/turtle' in accept or '*/*' in accept:
                            if is_dir:
                                entries = self.hub.list_dir(pod_path)
                                turtle_data = self._render_turtle(pod_path, entries)
                                return Response(turtle_data, mimetype='text/turtle', headers=resp_headers)

                        if 'application/json' in accept:
                            if is_dir:
                                entries = self.hub.list_dir(pod_path)
                                return jsonify({"entries": entries, **attr}), 200, resp_headers
                            return jsonify(attr), 200, resp_headers
                        
                        if not is_dir:
                            mt = "application/octet-stream"
                            if pod_path.lower().endswith((".crt", ".pem", ".cer")): mt = "application/x-x509-ca-cert"
                            return Response(self.hub.read_stream(pod_path), mimetype=mt, headers=resp_headers)
                        
                        return "@prefix ldp: <http://www.w3.org/ns/ldp#>.\n<> a ldp:BasicContainer.", 200, {**resp_headers, 'Content-Type': 'text/turtle'}

                elif request.method == 'PUT':
                    if self.hub.write(pod_path, request.get_data(), request.args.get('offset', 0, type=int)):
                        return "", 201
                elif request.method == 'POST':
                    if self.hub.create(pod_path, is_dir=(request.args.get('type') == 'container')):
                        return "", 201
                elif request.method == 'DELETE':
                    if self.hub.delete(pod_path):
                        return "", 204

            except Exception as e:
                return jsonify({"error": str(e)}), 500

            return jsonify({"error": "Not Found"}), 404

    def _render_turtle(self, pod_path: str, entries: list) -> str:
        """Render a directory listing as a Solid LDP Basic Container (Turtle)."""
        from datetime import datetime
        
        turtle = [
            "@prefix ldp: <http://www.w3.org/ns/ldp#>.",
            "@prefix terms: <http://purl.org/dc/terms/>.",
            "@prefix stat: <http://www.w3.org/ns/posix/stat#>.",
            "",
            "<> a ldp:BasicContainer;"
        ]

        if entries:
            for e in entries:
                full_p = os.path.join(pod_path, e)
                attr = self.hub.get_attr(full_p)
                is_dir = attr and bool(attr['st_mode'] & 0o40000)
                safe_e = e + "/" if is_dir else e
                turtle.append(f"<> ldp:contains <{safe_e}> .")
        else:
            turtle[-1] = turtle[-1].replace(";", ".")

        for e in entries:
            full_p = os.path.join(pod_path, e)
            attr = self.hub.get_attr(full_p)
            if not attr: continue
            is_dir = bool(attr['st_mtime'] != 0) # Simple heuristic for mock
            
            uri = e + "/" if bool(attr['st_mode'] & 0o40000) else e
            mtime = datetime.fromtimestamp(attr['st_mtime']).isoformat() + "Z" if attr['st_mtime'] else datetime.now().isoformat() + "Z"
            
            turtle.append("")
            turtle.append(f"<{uri}> a ldp:{'Container, ldp:BasicContainer' if bool(attr['st_mode'] & 0o40000) else 'Resource'};")
            turtle.append(f"   terms:modified \"{mtime}\";")
            if not bool(attr['st_mode'] & 0o40000):
                turtle.append(f"   stat:size {attr['st_size']}.")
            else:
                turtle[-1] = turtle[-1].replace(";", ".")

        return "\n".join(turtle)

    def run(self, port=8089):
        print(f"Pod Proxy running on http://0.0.0.0:{port}")
        print(f"Solid API: http://localhost:{port}/pod")
        print(f"WebDAV API: http://localhost:{port}/dav")
        from cheroot import wsgi
        server = wsgi.Server(("0.0.0.0", port), self.combined_app)
        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()
