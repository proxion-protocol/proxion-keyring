# Proxion Keyring Capabilities

`proxion-keyring` is the primary orchestration and management layer of the Proxion Suite. It acts as the local "Operating Environment" that bridges Identity, Storage, and Applications.

## 1. Resource Server (RS)
The Resource Server is the central gateway for all Proxion interactions. It interprets Capability Tokens and enforces access control.

- **Capability Enforcement**: All sensitive API endpoints are protected by `require_capability`.
- **Zeno-Trust Architecture**: No request is allowed without a valid, non-revoked token bound to the requester's key.
- **Suite Management API**: Programmatic endpoints for starting, stopping, and installing the 90+ suite applications.
- **Relay Proxying**: Handles the routing of requests across global network boundaries via the Proxion Relay hint system.

## 2. Identity Gateway
The Gateway manages the lifecycle of trust between the User and their devices.

- **Secure Handshaking**: QR-code based handshaking for linking phones, browsers, and extensions.
- **Capability Issuance**: Grants device-specific, attenuated tokens (e.g., granting a browser extension only 'search' and 'capture' rights).
- **Intent Resolution**: A secure flow where sensitive actions on one device (e.g., revoking a peer) must be "Resolved" (approved) on a primary trusted device (e.g., the Mobile App).

## 3. Suite Orchestrator
The CLI and Backend logic for managing a massive digital ecosystem.

- **90+ Application Registry**: A central `apps.json` defining metadata, ports, and storage paths for the world-class Proxion app library.
- **Managed Storage (Drive P:)**: Automatic orchestration of the **Proxion Drive** and mapping of persistent app data to prevent state-loss.
- **Dependency-Aware Launch**: Logic to ensure the "Core" services (Auth/Dashboard) are healthy before launching "Edge" services (Social/Media).
- **Concurrent Execution**: High-speed parallel orchestration of container stacks using batched threading.

## 4. Discovery & Federation
Logic for connecting independent Proxion Citadels.

- **Peer Management**: Storing and managing relationships with other Citadels and their certificate chains.
- **Federation Policy UI**: Visual management of granted and received capabilities across your network.
- **Relay Connectivity**: Maintaining active links to the Proxion Relay network for cross-CGNAT communication.

## 5. Security Services
- **Local Key Management**: Secure generation and storage of the Master Identity Key.
- **Token Redemption**: Full implementation of the DPoP flow for all incoming CLI and API requests.
- **Revocation Propagation**: Tracking and enforcing token revocation in real-time.
