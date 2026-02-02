
import os
import sys
import subprocess
import time

# Setup paths
sys.path.append(os.path.abspath("c:/Users/hobo/Desktop/Proxion/proxion-core/src"))
sys.path.append(os.path.abspath("c:/Users/hobo/Desktop/Proxion/proxion-keyring"))

def test_install():
    print("Testing AdGuard Installation...")
    
    # 1. Simulate the CLI call that server.py would make
    cmd = ["python", "-m", "proxion_keyring.cli", "suite", "install", "adguard"]
    
    # Needs correct env
    env = os.environ.copy()
    keyring_root = os.path.abspath("c:/Users/hobo/Desktop/Proxion/proxion-keyring")
    core_src = os.path.abspath("c:/Users/hobo/Desktop/Proxion/proxion-core/src")
    env["PYTHONPATH"] = f"{keyring_root}{os.pathsep}{core_src}{os.pathsep}{env.get('PYTHONPATH', '')}"
    
    try:
        res = subprocess.run(
            cmd, 
            cwd=keyring_root, 
            env=env, 
            capture_output=True, 
            text=True
        )
        print("STDOUT:", res.stdout)
        print("STDERR:", res.stderr)
        
        if res.returncode == 0:
            print("CLI returned SUCCESS")
        else:
            print("CLI returned FAILURE")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_install()
