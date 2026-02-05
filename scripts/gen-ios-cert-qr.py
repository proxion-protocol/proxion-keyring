import socket
import qrcode
import os
import shutil

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def main():
    # 1. Path to the certificate
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cert_path = os.path.join(repo_root, "integrations", "vaultwarden-integration", "proxion.crt")
    
    if not os.path.exists(cert_path):
        print(f"ERROR: Certificate not found at {cert_path}")
        return

    # 2. Local IP
    local_ip = get_local_ip()
    port = 8089 # Pod Proxy Port
    
    # URL for iOS enrollment
    # The Pod Proxy now supports .pem/.crt mimetypes
    url = f"http://{local_ip}:{port}/pod/{cert_path.replace('\\', '/')}"
    
    print("\n--- Proxion iOS SSL Enrollment ---")
    print(f"Target: {url}")
    print("\nScan the QR code below on your iPhone to install the certificate:")
    
    qr = qrcode.QRCode(version=1, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    
    # Print QR to terminal
    qr.print_ascii(invert=True)
    
    print("\nSteps for iPhone:")
    print("1. Scan the QR and tap 'Allow' to download the profile.")
    print("2. Go to Settings > General > VPN & Device Management.")
    print("3. Tap 'Proxion' (or the cert name) and tap 'Install'.")
    print("4. IMPORTANT: Go to Settings > General > About > Certificate Trust Settings.")
    print("5. Enable 'Full Trust' for the Proxion certificate.")
    print("\nBitwarden JWT errors should now be resolved.\n")

if __name__ == "__main__":
    main()
