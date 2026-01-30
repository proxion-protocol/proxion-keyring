# SCS Local Testing

This directory contains resources for testing Kleitikon against a local Solid Community Server (SCS).

## Prerequisites

- Docker
- Docker Compose

## Running SCS

### Option A: Docker (Recommended)
1. Start the server:
   ```bash
   docker-compose up -d
   ```

### Option B: Node.js (via NPX)
If you don't have Docker, you can run it directly:
```powershell
# Windows
./scripts/run_scs.ps1
```
Or manually:
```bash
npx -y @solid/community-server -f ./data -p 3200
```

---

The server will be available at `http://localhost:3200/`.

2. **Register a Pod**:
   - Go to http://localhost:3200/ in your browser.
   - **Docker**: Already set up? (No-setup config used).
     - Just register/login if prompt appears, or it might be open.
   - **NPX**: You will see the "Welcome to Solid" page.
     - Click **"Sign up"** / "Sign up for an account".
     - Enter an email/password (e.g. `user`/`password`).
     - Uncheck "Enforce email verification" if present (or just register).
     - Click "Register".
   - **Important**: After registering, you must **Create a Pod**.
     - Look for "Create Pod" or "Add Pod".
     - Name it `user` (or similar).
     - This generates your WebID: `http://localhost:3200/user/profile/card#me`.
   - **Note**: The page might say "Sign up for an account to get started". That text is usually a link or has a button nearby.
   - Use `http://localhost:3200/` as the issuer.
   - Your Pod root will be `http://localhost:3200/user/`.

3. **Run Kleitikon App**:
   - In `kleitikon/app`, run `npm run dev`.
   - Open the app.
   - Enter `http://localhost:3200/` as the OIDC Issuer.
   - Log in.
   - You should be prompted to authorize Kleitikon.

4. **Verify**:
   - Check container creation: `http://localhost:3200/user/kleitikon/`.
   - Check config: `http://localhost:3200/user/kleitikon/config/config.jsonld`.

## Troubleshooting

- **"Issuer not trusted"**: Ensure calling http://localhost:3200 from localhost.
- **"Storage root not found"**: Ensure the `pim:storage` triple exists in your WebID profile. SCS usually adds this by default. If not, use the manual fallback in the UI.

---

## Mobile Reachability Acceptance Test (WireGuard client on mobile)

This test validates the **"Functional Product"** requirement: a mobile device must be able to reach a service on your laptop via the secure channel (tunnel IP), not via `localhost`.

### Roles

| Component | Runs On | Description |
|-----------|---------|-------------|
| **Control Plane (CP)** | Laptop | Issues tickets, authorizes connections (Port 8787) |
| **Resource Server (RS)** | Laptop | Bootstraps WireGuard tunnel (Port 8788) |
| **Kleitikon App** | Laptop | User Interface for pairing |
| **Hidden Service** | Laptop | Simulation of a private app to access (Port 3100) |
| **Device RP Agent** | Laptop | *Temporarily runs on laptop* to act as the redeeming agent |
| **WireGuard Client** | Mobile | Connects to the tunnel provisioned by RS |

### Setup

1.  **Start Services**:
    ```bash
    # Tab 1: Control Plane
    cd kleitikon
    python -m cp.server # Runs on port 8787

    # Tab 2: Resource Server
    cd kleitikon
    python -m rs.server # Runs on port 8788

    # Tab 3: Web App
    cd kleitikon/app
    npm run dev -- --host 0.0.0.0 # Runs on port 3000 (usually) or 5173
    ```

2.  **Start a "Hidden" Service**:
    Run a simple HTTP server on your laptop that binds to `0.0.0.0` or your VPN interface IP.
    **Note**: We use port 3100 to avoid conflict with SCS (3000).
    ```bash
    mkdir secret_service
    echo "<h1>Hello from the Secure Tunnel!</h1>" > index.html
    python -m http.server 3100
    ```

### Execution

1.  **Pairing**:
    - Open Kleitikon App on your laptop.
    - Mint a ticket (or pick a static one for demo).
    - Use `agent/cli.py` (simulating the mobile device agent) to redeem:
      ```bash
      # On laptop (acting as RP agent)
      python agent/cli.py --as-uri http://localhost:8787 --pt <ticket_id> --rs-uri http://localhost:8788 --output wg.conf
      ```
    - This proves the flow: `CP Issue -> RP Redeem -> CP Token -> RS Bootstrap -> Connection Material`.

2.  **Connect Mobile**:
    - Transfer `wg.conf` to your mobile device (e.g., via QR code, email, etc).
    - Import into WireGuard for Android/iOS.
    - Activate the tunnel.

3.  **Verify**:
    - On mobile, open browser.
    - Navigate to `http://<LAPTOP_TUNNEL_IP>:3100`.
    - You should see "Hello from the Secure Tunnel!".

**Success Criteria**: Mobile reaches the service via the Tunnel IP.
