
import os
import sys
import subprocess
import json

# Setup paths
sys.path.append(os.path.abspath("c:/Users/hobo/Desktop/Proxion/proxion-core/src"))
sys.path.append(os.path.abspath("c:/Users/hobo/Desktop/Proxion/proxion-keyring"))

def check_status():
    integrations_dir = os.path.abspath("c:/Users/hobo/Desktop/Proxion/integrations")
    print(f"Scanning {integrations_dir}")

    # 1. Get ALL containers
    apps_with_containers = set()
    try:
        output = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.Names}}"]).decode()
        containers = [c.strip() for c in output.strip().split('\n') if c.strip()]
        print(f"Found containers: {containers}")
        for c in containers:
             apps_with_containers.add(c)
    except Exception as e:
        print(f"Docker Error: {e}")

    results = {}
    if os.path.exists(integrations_dir):
        for d in os.listdir(integrations_dir):
            if os.path.isdir(os.path.join(integrations_dir, d)):
                clean_id = d.replace("-integration", "")
                
                any_container = any(clean_id in c for c in apps_with_containers)
                
                if not any_container:
                    status = "UNINSTALLED"
                else:
                    try:
                        is_running = subprocess.run(
                            ["docker", "ps", "-q", "--filter", f"name={clean_id}"],
                            capture_output=True, text=True
                        ).stdout.strip() != ""
                        status = "RUNNING" if is_running else "STOPPED"
                    except:
                        status = "STOPPED"
                     
                results[d] = status
                if status != "UNINSTALLED":
                    print(f"App {clean_id}: {status}")

    # Check specifically for adguard
    print(f"AdGuard Status: {results.get('adguard-integration')}")

if __name__ == "__main__":
    check_status()
