import os
import sys
import time
import shutil
import subprocess

# Drive Q: for VS Code Settings Sync
MOUNT_POINT = "Q:" 
POD_PATH = "/stash/dev/vscode/"

# VS Code User Settings Path on Windows
VSCODE_USER_PATH = os.path.join(os.getenv('APPDATA'), "Code", "User")

FILES_TO_SYNC = [
    "settings.json",
    "keybindings.json",
    "snippets"
]

def ensure_mount():
    """Ensure the Pod vscode dir is mounted to Drive Q:"""
    if os.path.exists(MOUNT_POINT):
        return True
    
    print(f"[Proxion] Mounting VSCode Sync {POD_PATH} to {MOUNT_POINT}...")
    fuse_script = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../proxion-fuse/mount.py"))
    
    # Fire and forget mount
    subprocess.Popen(["python", fuse_script, MOUNT_POINT, POD_PATH])
    time.sleep(3)
    return os.path.exists(MOUNT_POINT)

def get_extensions():
    """Get list of installed VS Code extensions via CLI."""
    try:
        result = subprocess.run(["code", "--list-extensions"], capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception as e:
        print(f"Failed to list extensions: {e}")
    return ""

def sync_up():
    """Push local settings to Pod."""
    print("[Proxion] Syncing VS Code settings UP to Pod...")
    for item in FILES_TO_SYNC:
        local_path = os.path.join(VSCODE_USER_PATH, item)
        remote_path = os.path.join(MOUNT_POINT, item)
        
        if os.path.exists(local_path):
            try:
                if os.path.isdir(local_path):
                    if os.path.exists(remote_path):
                        shutil.rmtree(remote_path)
                    shutil.copytree(local_path, remote_path)
                else:
                    shutil.copy2(local_path, remote_path)
            except Exception as e:
                print(f"Failed to sync {item}: {e}")

    # Sync extensions list
    extensions = get_extensions()
    if extensions:
        with open(os.path.join(MOUNT_POINT, "extensions.txt"), "w") as f:
            f.write(extensions)
    print("Sync UP complete.")

def monitor_and_sync():
    """Monitor local files for changes and push to mount."""
    print(f"[Proxion] Monitoring VS Code settings in {VSCODE_USER_PATH}...")
    
    # Simple mtime based monitoring
    last_sync = time.time()
    
    try:
        while True:
            time.sleep(30) # Check every 30 seconds
            sync_needed = False
            
            for item in FILES_TO_SYNC:
                local_path = os.path.join(VSCODE_USER_PATH, item)
                if os.path.exists(local_path):
                    if os.path.getmtime(local_path) > last_sync:
                        sync_needed = True
                        break
            
            if sync_needed:
                sync_up()
                last_sync = time.time()
                
    except KeyboardInterrupt:
        print("Stopping VS Code sync.")

if __name__ == "__main__":
    if not os.path.exists(VSCODE_USER_PATH):
        print(f"Error: VS Code User path not found at {VSCODE_USER_PATH}")
        sys.exit(1)
        
    if ensure_mount():
        # Initial sync
        sync_up()
        monitor_and_sync()
    else:
        print("Failed to mount Proxion VSCode Sync.")
        sys.exit(1)
