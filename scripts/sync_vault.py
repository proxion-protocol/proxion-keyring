import os
import sys
import time
import shutil
import subprocess

# Local path to KeePassXC database (Expected)
LOCAL_VAULT = os.path.expanduser("~/Documents/ProxionVault.kdbx")
MOUNT_POINT = "T:" # Drive T for temporary sync
POD_PATH = "/stash/vault/"

def ensure_mount():
    """Ensure the Pod vault is mounted to Drive T:"""
    if os.path.exists(MOUNT_POINT):
        return True
    
    print(f"[Proxion] Mounting Vault {POD_PATH} to {MOUNT_POINT}...")
    fuse_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../proxion-fuse/mount.py"))
    
    # Fire and forget mount
    subprocess.Popen(["python", fuse_script, MOUNT_POINT, POD_PATH])
    time.sleep(3)
    return os.path.exists(MOUNT_POINT)

def monitor_and_sync():
    """Monitor local file for changes and push to mount."""
    if not os.path.exists(LOCAL_VAULT):
        print(f"[Proxion] Initializing Vault at {LOCAL_VAULT}...")
        # If it doesn't exist locally, try to pull from Pod
        remote_path = os.path.join(MOUNT_POINT, "vault.kdbx")
        if os.path.exists(remote_path):
            shutil.copy2(remote_path, LOCAL_VAULT)
            print("Successfully pulled vault from Pod.")
        else:
            print("No remote vault found. Please create a new .kdbx file at the path above.")
    
    last_mtime = os.path.getmtime(LOCAL_VAULT) if os.path.exists(LOCAL_VAULT) else 0

    print(f"[Proxion] Monitoring {LOCAL_VAULT}...")
    try:
        while True:
            time.sleep(5)
            if not os.path.exists(LOCAL_VAULT): continue
            
            current_mtime = os.path.getmtime(LOCAL_VAULT)
            if current_mtime > last_mtime:
                print(f"[Proxion] Change detected! Syncing to Pod...")
                remote_path = os.path.join(MOUNT_POINT, "vault.kdbx")
                try:
                    shutil.copy2(LOCAL_VAULT, remote_path)
                    print("Sync complete.")
                    last_mtime = current_mtime
                except Exception as e:
                    print(f"Sync failed: {e}")
    except KeyboardInterrupt:
        print("Stopping vault sync.")

if __name__ == "__main__":
    if ensure_mount():
        monitor_and_sync()
    else:
        print("Failed to mount Proxion Vault.")
        sys.exit(1)
