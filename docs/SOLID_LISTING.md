# Solid App Listing Checklist

proxion-keyring must satisfy [Solid Project app listing criteria](https://solidproject.org/apps).

---

## Required Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| Login with WebID + IdP of choice | ✅ | Issuer URL primary; WebID discovery best-effort |
| Data fetched from Pods | ✅ | Policies, devices, config read from Pod |
| Data stored in Pods | ✅ | All app data under `/proxion-keyring/` |
| Solid-spec compliant interactions | ✅ | Uses `@inrupt/solid-client` |

---

## Excluded Categories (must NOT apply)

| Category | Status |
|----------|--------|
| Harm / unethical uses | ❌ N/A |
| Hate | ❌ N/A |
| Malware / data theft | ❌ N/A |
| Illegal purposes | ❌ N/A |
| Sharing user info without consent | ❌ N/A |
| Known serious security issues | ❌ N/A |

---

## Privacy Statement

- No third-party sharing without explicit user consent.
- All data stored in user's Pod; user controls access.
- Receipts contain minimal metadata only.

---

## Interoperability

Tested with:
- Solid Community Server (local Docker)
- solidcommunity.net
- Chrome 120+, Firefox 120+

---

## Contact

When ready for listing, contact ODI per [Solid apps page](https://solidproject.org/apps).
