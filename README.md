# proxion-keyring

**Your Universal Digital Key Ring.**

proxion-keyring (Greek for "Keyring") is a privacy-first application that connects your devices instantly using your **Solid Pod** identity.

> **Status:** Phase 1 Complete (Windows & Linux Support)

## Why use proxion-keyring?

*   **Zero-Config Security:** Connect your laptop to your private network or devices without managing VPNs, IP addresses, or firewalls.
*   **"Install and Go":** No developer terminals. Just install, log in with your Solid Pod, and you're connected.
*   **Privacy by Default:** Your data stays in your Pod. No central servers tracking you.
*   **Secure:** Built on the **Proxion Protocol** and uses industry-standard **WireGuard®** encryption.

---

## 🚀 Getting Started

### Windows (Consumer Experience)

**Prerequisite:** A Solid Pod (e.g., from [solidcommunity.net](https://solidcommunity.net)).

1.  **Download & Install:**
    *   (Coming Soon: Signed MST/EXE Installer).
    *   For now, clone this repo and run `scripts/setup_wizard.ps1`.
    *   This will automatically install Dependncies (WireGuard) and set up the background service.

2.  **Run the Desktop App:**
    *   Start **proxion-keyring Desktop**.
    *   Log in with your Solid Pod URL.
    *   **Done.** The app sits in your tray, managing your connections automatically.

### Linux (Beta)

1.  **Dependencies:** Ensure `wireguard-tools` and `iproute2` are installed (`apt install wireguard-tools iproute2`).
2.  **Install:**
    ```bash
    pip install .
    proxion-keyring-rs  # Run as root/sudo
    ```
3.  **Use:** The Linux backend fully supports the Proxion Spec for creating and managing interfaces.

---

## 🛠 Features

### 1. The "Key Ring" Model
- **Identity = Connectivity.** If you possess the keys (Token) in your Pod, the door (Tunnel) opens automatically.
- **Revocation:** Lost a device? Click "Revoke" in your Dashboard, and access is cut instantly.

### 2. Native Desktop Experience (Electron)
- **Auto-pilot:** The app manages the Python backend process for you.
- **System Tray:** Minimizes out of your way, keeping the tunnel alive.
- **Persistent Login:** Stay connected without constant logins.

### 3. Cross-Platform Backend
- **Windows:** Uses a hidden Windows Service + Winget for dependency management.
- **Linux:** Uses `ip` and `wg` commands with robust sudo handling.

---

## 🔐 Security & Compliance

proxion-keyring is the reference implementation of the **Proxion Universal Architecture**.

*   ✅ **Normative Invariants Verified:**
    *   No Authority Amplification (Attenuation)
    *   Single-Use Tickets
    *   Finite Authority (Time-bound access)
    *   Contextual Authorization
    *   Audience Binding
*   ✅ **Fail-Closed Design:** Any error results in immediate denial of access.

---

## For Developers

### Running from Source

**1. Backend (Python)**
```bash
# Install package
pip install -e .
# Run Server
python -m proxion-keyring.rs.server
```

**2. Frontend (React/Electron)**
```bash
cd dashboard
npm install
npm run electron:dev  # Runs Vite + Electron together
```

---

## License
Apache-2.0. See [LICENSE](LICENSE).

---
*WireGuard is a registered trademark of Jason A. Donenfeld.*
