import os
import sys
import subprocess
import re
from abc import ABC, abstractmethod

class OSAdapter(ABC):
    @abstractmethod
    def get_active_interface_index(self):
        """Find the interface index for the primary internet connection."""
        pass

    @abstractmethod
    def set_dns(self, interface_index, addresses):
        """Set DNS server addresses for the given interface."""
        pass

    @abstractmethod
    def reset_dns(self, interface_index):
        """Reset DNS to automatic (DHCP) for the given interface."""
        pass
    
    @abstractmethod
    def get_dns(self, interface_index):
        """Get DNS server addresses for the given interface."""
        pass

    @abstractmethod
    @abstractmethod
    def get_docker_compose_cmd(self, app_path, local_storage, action=["up", "-d"]):
        """Return the base docker-compose command with necessary overrides."""
        pass

    @abstractmethod
    def check_docker_health(self):
        """Check for common Docker misconfigurations that block Proxion."""
        pass

class WindowsAdapter(OSAdapter):
    def get_active_interface_index(self):
        # Using PowerShell to find the default route's interface
        cmd = ["powershell", "-Command", "(Get-NetRoute -DestinationPrefix 0.0.0.0/0 | Select-Object -First 1).InterfaceIndex"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return int(res.stdout.strip())
        except:
            return None

    def is_admin(self):
        """Check if the current process has administrative privileges."""
        import ctypes
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    def _elevate_ps(self, ps_cmd):
        """Execute a PowerShell command with UAC elevation if needed."""
        if self.is_admin():
            print(f"OSAdapter: Already elevated, running: {ps_cmd}")
            return subprocess.run(["powershell", "-Command", ps_cmd])
            
        print(f"OSAdapter: Requesting elevation for: {ps_cmd}")
        elevated_cmd = f"Start-Process powershell -Verb RunAs -ArgumentList '-Command \"{ps_cmd}\"'"
        # Use shell=True for start-process to ensure it detaches properly from the parent console if needed
        return subprocess.run(["powershell", "-Command", elevated_cmd])

    def set_dns(self, interface_index, addresses):
        if not isinstance(addresses, list):
            addresses = [addresses]
        addr_str = ",".join(addresses)
        ps_cmd = f"Set-DnsClientServerAddress -InterfaceIndex {interface_index} -ServerAddresses {addr_str}"
        return self._elevate_ps(ps_cmd)

    def reset_dns(self, interface_index):
        ps_cmd = f"Set-DnsClientServerAddress -InterfaceIndex {interface_index} -ResetServerAddresses"
        return self._elevate_ps(ps_cmd)

    def get_dns(self, interface_index):
        # Using PowerShell to get the DNS server addresses
        ps_cmd = f"(Get-DnsClientServerAddress -InterfaceIndex {interface_index} -AddressFamily IPv4).ServerAddresses"
        cmd = ["powershell", "-Command", ps_cmd]
        res = subprocess.run(cmd, capture_output=True, text=True)
        try:
            # Output might be a comma-separated list or multiple lines
            addrs = [a.strip() for a in res.stdout.replace('\n', ',').split(',') if a.strip()]
            return addrs
        except:
            return []

    def get_docker_compose_cmd(self, app_path, local_storage, action=["up", "-d"]):
        # On Windows, we generate the proxion-local override to bypass P: drive
        override_content = "version: '3'\nservices:\n"
        
        try:
            full_content = ""
            for cf in ["docker-compose.yml", "docker-compose.override.yml"]:
                cf_path = os.path.join(app_path, cf)
                if os.path.exists(cf_path):
                    with open(cf_path, "r") as f:
                        full_content += f.read() + "\n"
            
            # Parse Services and their P:/ volumes
            service_blocks = re.split(r"^  ([\w\-]+):", full_content, flags=re.MULTILINE)
            for i in range(1, len(service_blocks), 2):
                svc_name = service_blocks[i]
                svc_body = service_blocks[i+1]
                
                p_vols = re.findall(r"^[ ]+- (P:/[^ \n]+)", svc_body, re.MULTILINE)
                if p_vols:
                    override_content += f"  {svc_name}:\n    volumes:\n"
                    for v in p_vols:
                        # Multi-Source Smart Resolution
                        rel_v = v.replace("P:/", "").lstrip("/")
                        resolved_local = None
                        
                        # Load sources to find match
                        from .config import load_config
                        config = load_config()
                        sources = config.get("stash_sources", [])
                        
                        # Check specific source names
                        for s in sources:
                            s_name = s.get("name").replace(" ", "_")
                            if rel_v == s_name or rel_v.startswith(s_name + "/"):
                                s_path = s.get("path")
                                sub = rel_v[len(s_name):].lstrip("/")
                                resolved_local = os.path.join(s_path, sub).replace("\\", "/")
                                break
                        
                        # Fallback to primary
                        if not resolved_local:
                            resolved_local = v.replace("P:/", local_storage + "/")
                            
                        override_content += f"      - {resolved_local}\n"
                        # Ensure host directory exists (if it's a local Disk)
                        if ":" in resolved_local:
                             host_dir = os.path.dirname(resolved_local)
                             if host_dir and not host_dir.endswith(":"):
                                 os.makedirs(host_dir, exist_ok=True)
            
            # Phase 5: Port Clearing for Tunneled Services
            # If any service uses 'network_mode: service:...', we must clear its ports to avoid conflicts
            for i in range(1, len(service_blocks), 2):
                svc_name = service_blocks[i]
                svc_body = service_blocks[i+1]
                if "network_mode: \"service:" in svc_body or "network_mode: service:" in svc_body:
                    if f"  {svc_name}:" not in override_content:
                        override_content += f"  {svc_name}:\n"
                    override_content += "    ports: []\n"

            # Debug log for orchestration
            with open(os.path.join(app_path, "proxion_debug.log"), "a") as f:
                import datetime
                f.write(f"[{datetime.datetime.now()}] Orchestrate with local_storage={local_storage}\n")
                f.write(f"Generated Override:\n{override_content}\n")

            # Use 'docker compose' (v2) on Windows to avoid API version mismatches (1.25 error)
            # Preference: docker compose > docker-compose
            cmd = ["docker", "compose", "-f", "docker-compose.yml"]
            if os.path.exists(os.path.join(app_path, "docker-compose.override.yml")):
                cmd += ["-f", "docker-compose.override.yml"]
                
            # Only verify and write if we have actual services overrides
            if override_content.strip() != "version: '3'\nservices:":
                tmp_override = os.path.join(app_path, "docker-compose.proxion-local.yml")
                with open(tmp_override, "w") as f:
                    f.write(override_content)
                cmd += ["-f", "docker-compose.proxion-local.yml"]
                
            cmd += action
            return cmd
        except Exception as e:
            # Fallback to standard if override fails
            return ["docker", "compose", "up", "-d"]

    def check_docker_health(self):
        """Verify Docker Desktop proxy settings on Windows."""
        import json
        settings_path = os.path.expandvars(r"%APPDATA%\Docker\settings.json")
        results = {"status": "PASS", "warnings": []}
        
        if not os.path.exists(settings_path):
            return results # Not Docker Desktop?
            
        try:
            with open(settings_path, "r") as f:
                settings = json.load(f)
                
            proxy_mode = settings.get("proxyHttpMode", "system")
            transparent_proxy = settings.get("vpnKitTransparentProxy", False)
            
            if transparent_proxy:
                results["status"] = "WARN"
                results["warnings"].append("vpnKitTransparentProxy is ACTIVE. This may block Docker pulls if a VPN is used.")
                
            if proxy_mode == "system":
                # Check if host actually has a system proxy
                res = subprocess.run(["netsh", "winhttp", "show", "proxy"], capture_output=True, text=True)
                if "Direct access" not in res.stdout:
                    results["status"] = "WARN"
                    results["warnings"].append("System Proxy detected. Docker is inheriting this, which may cause timeouts.")
                    
        except Exception as e:
            results["warnings"].append(f"Failed to audit Docker settings: {e}")
            
        return results

class LinuxAdapter(OSAdapter):
    def get_active_interface_index(self):
        # Heuristic using ip route
        cmd = ["sh", "-c", "ip route show default | awk '{print $5}'"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.stdout.strip()

    def set_dns(self, interface_index, addresses):
        # Assuming systemd-resolved (resolvectl)
        addr_str = " ".join(addresses) if isinstance(addresses, list) else addresses
        cmd = ["sudo", "resolvectl", "dns", str(interface_index), addr_str]
        return subprocess.run(cmd)

    def reset_dns(self, interface_index):
        cmd = ["sudo", "resolvectl", "revert", str(interface_index)]
        return subprocess.run(cmd)

    def get_dns(self, interface_index):
        cmd = ["sh", "-c", f"resolvectl dns {interface_index} | awk '{{print $4}}'"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return [res.stdout.strip()] if res.stdout.strip() else []

    def get_docker_compose_cmd(self, app_path, local_storage, action=["up", "-d"]):
        # Linux can typically mount FUSE drives directly, so no override needed
        return ["docker-compose"] + action

    def check_docker_health(self):
        return {"status": "PASS", "warnings": []}

class MacAdapter(OSAdapter):
    def get_active_interface_index(self):
        # On Mac, we identify the service name for networksetup
        cmd = ["sh", "-c", "networksetup -listallnetworkservices | grep -v '*' | head -n 1"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.stdout.strip() or "Wi-Fi"

    def set_dns(self, interface_name, addresses):
        if not isinstance(addresses, list):
            addresses = [addresses]
        cmd = ["sudo", "networksetup", "-setdnsservers", interface_name] + addresses
        return subprocess.run(cmd)

    def reset_dns(self, interface_name):
        cmd = ["sudo", "networksetup", "-setdnsservers", interface_name, "Empty"]
        return subprocess.run(cmd)

    def get_docker_compose_cmd(self, app_path, local_storage, action=["up", "-d"]):
        # Mac, like Linux, can usually see FUSE mounts via macFUSE directly
        return ["docker-compose"] + action

    def check_docker_health(self):
        return {"status": "PASS", "warnings": []}

def get_adapter():
    if os.name == 'nt':
        return WindowsAdapter()
    elif sys.platform == 'darwin':
        return MacAdapter()
    else:
        return LinuxAdapter()
