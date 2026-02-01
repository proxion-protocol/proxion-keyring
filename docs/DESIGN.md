# proxion-keyring Design

A **Solid-compatible application** for authorizing and managing **trusted device connections** using the user's Solid Pod for policy, receipts, and (optionally) audit.

> **Positioning:** proxion-keyring is an *app*, not a VPN product. It uses Proxion (UI spec) as the control-plane protocol and treats secure-channel establishment (e.g., WireGuard) as a pluggable data-plane instantiation.

---

## 1. Goals

### 1.1 Primary Goals

* Provide a Solid-compatible, user-centric experience for **pairing devices** and **granting/revoking connection authorizations**.
* Store app-generated data (policies, consent receipts, optional audit) in the user's **Solid Pod**.
* Allow users to log in with a **WebID** and an **Identity Provider of their choice** (Solid-OIDC/WebID-OIDC).
* Use Proxion UI semantics for:
  * single-use, short-lived **permission tickets**
  * issuance of **capability tokens** (explicit permissions + contextual caveats)
  * attenuation and revocation
  * fail-closed validation

### 1.2 Non-Goals

* No claim to be a general VPN provider.
* No requirement that every participant operate a self-hosted Pod or self-hosted IdP.
* No requirement that Solid be online during data transfer.
* No forced data plane: WireGuard is one instantiation; other DPs may exist.

---

## 2. High-Level Architecture

### 2.1 Components

| Component | Description |
|-----------|-------------|
| **proxion-keyring App (Web UI)** | Browser app. Solid login, device roster, policies, receipts. |
| **Control Plane (CP)** | Proxion lifecycle: ticket issuance, redemption, token issuance. |
| **Resource Server (RS)** | Token validation, connection material for DP. |
| **Device Agent (RP)** | CLI on devices being paired. Redeems tickets, applies config. |

### 2.2 Trust Boundaries

* User's Pod = canonical store for proxion-keyring app state.
* CP validates and writes only minimized state.
* DP is independent; CP authorizes "bootstrap of secure channel."

---

## 3. Data Model in Solid Pod

Container layout under discovered storage root:

```
/proxion-keyring/
  config/config.jsonld
  devices/index.jsonld
  devices/<device_id>.jsonld
  policies/<policy_id>.jsonld
  receipts/<receipt_id>.jsonld
  audit/<event_id>.jsonld
```

### Device Descriptor

```json
{
  "@context": ["https://www.w3.org/ns/solid/terms"],
  "type": "proxion-keyringDevice",
  "device_id": "did:peer:...",
  "label": "My Laptop",
  "created_at": 0,
  "keys": { "holder_pub": "..." }
}
```

### Policy Resource

```json
{
  "type": "proxion-keyringPolicy",
  "policy_id": "pol-...",
  "applies_to": { "device_id": "did:peer:..." },
  "permits": [{ "action": "channel.bootstrap", "resource": "rs:wg0" }],
  "caveats": [
    { "type": "ip_allowlist", "allowed": ["10.0.0.0/24"] },
    { "type": "time_window", "not_before": 0, "not_after": 0 }
  ]
}
```

### Consent Receipt

```json
{
  "type": "proxion-keyringReceipt",
  "receipt_id": "rcpt-...",
  "who": { "webid": "https://...#me" },
  "what": { "action": "channel.bootstrap", "resource": "rs:wg0" },
  "to": { "device_id": "did:peer:..." },
  "issued_at": 0,
  "expires_at": 0,
  "token_id": "sha256:..."
}
```

**Privacy**: Receipts MUST NOT include RS endpoints or network metadata.

---

## 4. Control-Plane Protocol (Proxion UI)

### 4.1 Ticket Issuance

RO authenticates → CP issues PT → App produces QR with `as_uri`, `pt`, `aud_hint`.

### 4.2 Ticket Redemption

RP redeems PT with PoP (Ed25519 sig over `ticket_id || aud || nonce || ts`) → CP evaluates policy → issues token → browser writes receipt.

### 4.3 Channel Bootstrap

RP presents token to RS → RS validates → returns `proxion-keyringConnectionMaterial`.

### 4.4 Revocation

RO revokes via UI → CP writes revocation entry → RS enforces.

---

## 5. WireGuard Instantiation

### Actions

* `wg.peer.add` / `wg.peer.remove` on `wg:interface:wg0`

### RS Response Schema

```json
{
  "type": "proxion-keyringConnectionMaterial",
  "dp": "wireguard",
  "interface": "wg0",
  "client": { "address": "10.0.0.2/32", "dns": ["10.0.0.1"] },
  "server": { "endpoint": "example.com:51820", "pubkey": "..." },
  "allowed_ips": ["10.0.0.0/24"],
  "expires_at": 1234567890
}
```

Default mode: `NO_MUTATION`.

---

## 6. Threat Model

See [THREAT_MODEL.md](THREAT_MODEL.md).
