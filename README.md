# Kleitikon

A Solid-compatible application for authorizing and managing trusted device
connections using the user’s Solid Pod for policy, receipts, and optional audit.

Kleitikon is an app, not a VPN product. It instantiates the Proxion Universal
Architecture (UI) as the control-plane protocol and treats secure-channel
establishment (e.g., WireGuard) as a pluggable data-plane instantiation.

## What is stored in the Pod

All Kleitikon state is stored under `/kleitikon/` in the user’s Pod:

- `/kleitikon/policies/`
- `/kleitikon/receipts/`
- `/kleitikon/audit/` (optional)
- `/kleitikon/devices/`
- `/kleitikon/config/`

## Security

- Permission Tickets (PT) are single-use and short-lived.
- Capability tokens include audience binding and proof-of-possession.
- Contextual caveats are enforced and fail closed.
- Optional revocation is supported and enforced by the RS.

## Data sharing

Kleitikon does not share user data with third parties without explicit consent.

## Repo layout

- `docs/` design, threat model, Solid listing checklist
- `app/` web UI (Solid login and Pod setup)
- `cp/` control-plane service (stub)
- `rs/` resource server for secure-channel bootstrap (stub)
- `agent/` device agent (stub)

## Development (Phase 1)

The web app is a minimal Solid login and Pod bootstrap flow.

```
cd app
npm install
npm run dev
```

## License

Apache-2.0
