# Kleitikon Roadmap

This document outlines the planned trajectory for Kleitikon, evolving from its current verified MVP state toward a robust, production-ready ecosystem.

## Phase 1: Hardware & Kernel Integration (The "Real" WireGuard)

The current implementation uses a "Mock" Resource Server to verify tokens. Our next technical leap is actual network tunnel management.

- **WireGuard Execution**: Transition from `NO_MUTATION` to active `wg set` commands on Linux/macOS/Windows backends.
- **Dynamic Port Management**: Automatically negotiate and open local ports for tunnels without human intervention.
- **Cross-Platform RS**: Package the Resource Server as a lightweight binary for embedded systems (Routers/NAS).

## Phase 2: Secure Remote Development (The Antigravity Link)

We have a specific use case: **Safely routing the Antigravity VS Code extension (port 3000) to a mobile device over the internet.**

### The Problem
Exposing port 3000 to the public internet is a critical security risk (RCE, XSS). Using standard port forwarding or simple proxies lacks fine-grained authorization and identity verification.

### The Kleitikon Solution
1. **Private Tunneling**: Kleitikon will establish a peer-to-peer WireGuard tunnel between the Desktop/Server (running VS Code) and the Mobile Device.
2. **Solid-OIDC Gatekeeping**: Only the user authenticated via their Solid Pod can "Redeem" the ticket to join this tunnel.
3. **Implicit Auth**: The VS Code extension on port 3000 will only be reachable via the tunnel's private IP. The public internet never sees the port.
4. **Auditability**: Every time the mobile device connects to the dev server, a receipt is written to the Pod, ensuring a permanent, user-owned history of all remote access sessions.

## Phase 3: Advanced Policy UI & Automation

Moving beyond "Default Allow" in the browser:

- **Policy Manager**: A dedicated screen in the Kleitikon app to view, edit, and revoke individual device permissions.
- **Time-Bound Keys**: Automatically expire connection tickets and tokens.
- **Location-Aware Context**: Policies that only allow connections when the device is at a trusted GPS location or on a specific network.

## Phase 4: Ecosystem & Listing

- **Solid App Listing**: Official submission to the Solid project's app gallery.
- **Universal SDK**: A library for other developers to integrate "Kleitikon Support" into their own hardware/software, essentially becoming a "Login with Solid" for the physical world.
- **Mesh Groups**: Orchestrating groups of devices to create private, decentralized "Local Area Networks" across the globe.
