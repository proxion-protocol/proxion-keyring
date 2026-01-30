# Kleitikon Threat Model

## Adversaries

| ID | Adversary | Description |
|----|-----------|-------------|
| A1 | QR Eavesdropper | Sees permission ticket via shoulder-surfing or camera |
| A2 | MitM | Between RP and CP/RS |
| A3 | Compromised RP | Device with stolen/leaked keys |
| A4 | Honest-but-Curious CP | CP host that follows protocol but logs excessively |

---

## Threats and Mitigations

| Threat | Mitigation |
|--------|------------|
| **T1: PT replay** | PT is single-use + short TTL; redemption invalidates |
| **T2: Token theft** | Audience binding + PoP (Ed25519 signature) |
| **T3: Phishing** | RO sees RP claims + explicit approve in UI |
| **T4: Over-permission** | Default deny; explicit consent per action/resource |
| **T5: Correlation** | Pairwise device IDs; no global identifiers |
| **T6: Data exfiltration** | Pod-first storage; no third-party sharing without consent |

---

## Invariants (from Proxion UI)

* **I1**: No authority amplification.
* **I2**: Single-use tickets.
* **I3**: Finite authority (time-bounded).
* **I4**: Contextual authorization (not just token possession).
* **I5**: No global identity requirement.
* **I6**: Audience + PoP binding.

---

## Privacy Posture

* Receipts contain only `token_id`, action, resource, time bounds.
* **No endpoints, IPs, or network metadata** in Pod resources.
* RS must NOT log token contents or keys.
