# Kleitikon Threat Model (Minimal)

## Adversaries

- QR eavesdropper (sees PT)
- MitM between RP and CP/RS
- Compromised RP device
- Honest-but-curious CP host

## Mitigations (must implement)

- PT single-use + TTL
- Token audience binding + proof-of-possession
- Fail-closed RS validation
- Minimize Pod data; no third-party sharing without consent
- Revocation list + DP teardown
