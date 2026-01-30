# Kleitikon

**Solid-based device pairing and connection authorization.**

Kleitikon is a Solid-compatible application that lets you pair devices and manage connection authorizations using your Solid Pod for policy, receipts, and configuration.

---

## Solid Compatibility

- **Login**: Enter your OIDC issuer (IdP URL). WebID discovery is best-effort; if it fails, you'll be prompted for your issuer.
- **Data stored in your Pod**: All app data lives under `/kleitikon/` in your Pod:
  - `/kleitikon/config/` — App configuration
  - `/kleitikon/devices/` — Registered device descriptors
  - `/kleitikon/policies/` — Authorization policies
  - `/kleitikon/receipts/` — Consent receipts
  - `/kleitikon/audit/` — Optional audit log
- **Data portability**: Everything is stored under `/kleitikon/` and can be removed at any time.

---

## Privacy

- **No third-party sharing** without your explicit consent.
- Receipts contain only minimal metadata (token ID, action, time bounds) — no IP addresses or network endpoints.
- Pairwise device identifiers; no global tracking.

---

## Security

- **Permission Tickets (PT)**: Single-use, short TTL.
- **Proof-of-Possession (PoP)**: Ed25519 signature required for token redemption.
- **Revocation**: Supported via revocation lists.
- **Fail-closed**: Any authorization failure results in denial.
- **Default Policy**: **"Default Allow" is for Demo Mode only** (when no policy exists). Production mode will be Default Deny unless an explicit policy is present.

---

## Backends (Developer/Advanced)

Kleitikon treats secure-channel establishment as pluggable. The initial backend is **WireGuard**:

- RS validates tokens and returns connection material.
- WireGuard mutation is disabled by default (`NO_MUTATION`).

---

## Mesh Orchestration (Concept)

Kleitikon acts as "middleware for mesh apps."
- **Solid Pod**: Stores device roster, policies, revocations, and consent receipts (orchestrator).
- **Control Plane**: Enforces policy to authorize tunnel formation.
- **Data Plane (RS)**: Provisions the actual connectivity (e.g., WireGuard).

Future versions will support explicit **Mesh Groups** in the Pod to orchestrate multi-device connectivity.

---

## How to Try It

### Prerequisites

- A Solid Pod (e.g., from [solidcommunity.net](https://solidcommunity.net))
- Node.js 18+ (for the web app)
- Python 3.10+ (for CP/RS services)

### Run the Web App

```bash
cd app
npm install
npm run dev
```

Open the displayed URL, enter your OIDC issuer, and log in.

### Run the Control Plane (stub)

```bash
cd cp
pip install -e ../proxion-core
python -m cp
```

### Run the Resource Server (stub)

```bash
cd rs
pip install -e ../proxion-core
python -m rs
```

---

## Tested With

- **Automated Tests**: Unit tests + mocked Pod routines (`pytest`, `npm test`)
- **Integration**: Manual verification with Solid Community Server (local via Docker) — see `scripts/README.md`
- [solidcommunity.net](https://solidcommunity.net)
- Chrome 120+, Firefox 120+

### Dependencies (pinned)

- `@inrupt/solid-client-authn-browser`: 1.30.0
- `@inrupt/solid-client`: 1.30.0
- `vite`: 5.4.0

---

## License

Apache-2.0. See [LICENSE](LICENSE).

---

## Issue Tracker

[GitHub Issues](https://github.com/proxion-protocol/kleitikon/issues)
