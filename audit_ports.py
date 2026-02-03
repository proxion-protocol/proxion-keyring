"""
Port Configuration Audit Script
Compares docker-compose.yml port mappings with apps.json entries
"""
import json
import os
import re
from pathlib import Path

# Load apps.json
apps_json_path = Path(r"c:\Users\hobo\Desktop\Proxion\proxion-keyring\dashboard\src\data\apps.json")
with open(apps_json_path, 'r', encoding='utf-8') as f:
    apps = json.load(f)

# Build lookup: integration_id -> expected_port
app_ports = {app['id']: app['port'] for app in apps}

# Scan integrations directory
integrations_dir = Path(r"c:\Users\hobo\Desktop\Proxion\integrations")
mismatches = []

for integration_folder in integrations_dir.iterdir():
    if not integration_folder.is_dir():
        continue
    
    integration_id = integration_folder.name
    compose_file = integration_folder / "docker-compose.yml"
    
    if not compose_file.exists():
        continue
    
    # Read docker-compose.yml
    with open(compose_file, 'r', encoding='utf-8') as f:
        compose_content = f.read()
    
    # Extract port mappings (format: "HOST:CONTAINER" or HOST:CONTAINER)
    port_pattern = r'^\s*-\s*["\']?(\d+):(\d+)["\']?\s*$'
    matches = re.findall(port_pattern, compose_content, re.MULTILINE)
    
    if not matches:
        continue
    
    # Get first port mapping (primary service port)
    host_port, container_port = matches[0]
    host_port = int(host_port)
    
    # Compare with apps.json
    expected_port = app_ports.get(integration_id)
    
    if expected_port is not None and expected_port != host_port:
        mismatches.append({
            'integration': integration_id,
            'compose_file': str(compose_file),
            'actual_port': host_port,
            'expected_port': expected_port
        })

# Report findings
print("=" * 80)
print("PORT CONFIGURATION AUDIT")
print("=" * 80)

if not mismatches:
    print("\n✅ All port configurations match between docker-compose.yml and apps.json")
else:
    print(f"\n❌ Found {len(mismatches)} port mismatches:\n")
    for mismatch in mismatches:
        print(f"Integration: {mismatch['integration']}")
        print(f"  File: {mismatch['compose_file']}")
        print(f"  Docker Compose Port: {mismatch['actual_port']}")
        print(f"  apps.json Port: {mismatch['expected_port']}")
        print()

print("=" * 80)
