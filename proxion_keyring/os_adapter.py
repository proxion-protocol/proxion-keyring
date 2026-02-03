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
    def get_docker_compose_cmd(self, app_path, local_storage, action=["up", "-d"]):
        """Return the base docker-compose command with necessary overrides."""
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

    def _elevate_ps(self, ps_cmd):
        elevated_cmd = f"Start-Process powershell -Verb RunAs -ArgumentList '-Command \"{ps_cmd}\"'"
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
                        local_v = v.replace("P:/", local_storage + "/")
                        override_content += f"      - {local_v}\n"
                        # Ensure host directory exists
                        host_part = local_v.split(":")[0]
                        os.makedirs(host_part.replace("/", "\\"), exist_ok=True)
            
            cmd = ["docker-compose", "-f", "docker-compose.yml"]
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
            return ["docker-compose", "up", "-d"]

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

    def get_docker_compose_cmd(self, app_path, local_storage, action=["up", "-d"]):
        # Linux can typically mount FUSE drives directly, so no override needed
        return ["docker-compose"] + action

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

def get_adapter():
    if os.name == 'nt':
        return WindowsAdapter()
    elif sys.platform == 'darwin':
        return MacAdapter()
    else:
        return LinuxAdapter()
