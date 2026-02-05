import subprocess
import shutil
import os
import sys

def check_docker():
    """Verify Docker is installed and running."""
    if not shutil.which("docker"):
        return False, "Docker is not installed. Please install Docker Desktop."
    try:
        subprocess.run(["docker", "ps"], check=True, capture_output=True)
        
        # New: Check for network health (proxies)
        try:
            from proxion_keyring.os_adapter import get_adapter
            adapter = get_adapter()
            health = adapter.check_docker_health()
            if health["status"] == "WARN":
                return True, f"Docker is running, but with warnings: {'; '.join(health['warnings'])}"
        except:
            pass # Module not in path yet?
            
        return True, "Docker is running."
    except subprocess.CalledProcessError:
        return False, "Docker is installed but not running. Please start Docker Desktop."

def check_wsl():
    """Verify WSL2 status on Windows."""
    if os.name != 'nt':
        return True, "Not on Windows, skipping WSL check."
    
    if not shutil.which("wsl"):
        return False, "WSL is not installed. Proxion requires WSL2 on Windows."
    
    try:
        # Check if we have any distributions
        result = subprocess.run(["wsl", "--list", "--quiet"], capture_output=True, text=True)
        if result.stdout.strip():
            return True, "WSL2 is ready."
        return False, "WSL is installed but no distributions found (needed for Docker)."
    except:
        return False, "Failed to verify WSL status."

def check_fuse():
    """Verify WinFSP/FUSE is installed."""
    if os.name == 'nt':
        # Check for WinFSP in common location
        winfsp_path = r"C:\Program Files (x86)\WinFSP"
        if os.path.exists(winfsp_path):
            return True, "WinFSP (FUSE) is installed."
        return False, "WinFSP is missing. Please install WinFSP to enable Drive P: mounting."
    else:
        # Check for fuse (linux/mac)
        if shutil.which("fusermount") or os.name == 'posix':
            return True, "FUSE is ready."
        return False, "FUSE (fusermount) is missing."

def check_wireguard():
    """Verify WireGuard is installed."""
    if os.name == 'nt':
        # Check for wireguard in path or common location
        if shutil.which("wg"):
            return True, "WireGuard CLI (wg) is in PATH."
        if os.path.exists(r"C:\Program Files\WireGuard\wireguard.exe"):
            return True, "WireGuard application found."
        return False, "WireGuard is missing. Please install WireGuard from wireguard.com."
    else:
        if shutil.which("wg"):
            return True, "WireGuard is installed."
        return False, "WireGuard (wg) is missing."

def run_all_checks():
    results = {
        "docker": check_docker(),
        "wsl": check_wsl(),
        "fuse": check_fuse(),
        "wireguard": check_wireguard()
    }
    return results

def install_dependency(dep_name: str) -> tuple[bool, str]:
    """Trigger installation or startup of a missing dependency."""
    if os.name != 'nt':
        return False, "Auto-install only supported on Windows via winget."
    
    # Special case for Docker: if it's installed but not running, try starting it
    if dep_name == "docker":
        docker_exe = r"C:\Program Files\Docker\Docker\Docker Desktop.exe"
        if os.path.exists(docker_exe):
            try:
                subprocess.Popen([docker_exe], start_new_session=True)
                return True, "Docker Desktop is being started. Please wait a moment for it to initialize."
            except Exception as e:
                return False, f"Failed to start Docker Desktop: {str(e)}"

    commands = {
        "docker": ["winget", "install", "Docker.DockerDesktop", "--accept-package-agreements", "--accept-source-agreements"],
        "wireguard": ["winget", "install", "WireGuard.WireGuard", "--accept-package-agreements", "--accept-source-agreements"],
        "fuse": ["winget", "install", "WinFSP.WinFSP", "--accept-package-agreements", "--accept-source-agreements"],
        "wsl": ["wsl", "--install", "--no-launch"]
    }
    
    if dep_name not in commands:
        return False, f"Unknown dependency: {dep_name}"

    try:
        # Run winget/wsl install
        result = subprocess.run(commands[dep_name], capture_output=True, text=True)
        if result.returncode == 0:
            return True, f"Successfully initiated installation for {dep_name}. Please follow any on-screen prompts."
        elif "already installed" in (result.stdout + result.stderr).lower():
            return True, f"{dep_name} is already installed. If it's not running, please start it manually."
        else:
            return False, f"Installation failed for {dep_name}: {result.stderr or result.stdout}"
    except Exception as e:
        return False, f"Error triggering installation: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        dep = sys.argv[2]
        ok, msg = install_dependency(dep)
        print(msg)
        sys.exit(0 if ok else 1)

    results = run_all_checks()
    for key, (status, msg) in results.items():
        icon = "✅" if status else "❌"
        print(f"{icon} {key.upper()}: {msg}")
    
    if all(status for status, msg in results.values()):
        print("\n🚀 System is ready for Proxion.")
    else:
        print("\n⚠️  Some dependencies are missing. Please fix them to continue.")
        sys.exit(1)
