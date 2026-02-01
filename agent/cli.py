"""Device RP CLI for proxion-keyring (Phase 3.5).

Minimal CLI that redeems a PT and fetches connection material.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from dataclasses import dataclass


from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


@dataclass
class QRPayload:
    """Simulated QR payload."""
    as_uri: str
    pt: str


def generate_keypair() -> tuple[str, str]:
    """Generate an Ed25519 keypair.

    Returns:
        Tuple of (public_key_hex, private_key_hex).
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Serialize private key to hex (raw bytes)
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    
    # Serialize public key to hex (raw bytes)
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    return public_bytes.hex(), private_bytes.hex()


def sign_pop(private_key_hex: str, ticket_id: str, aud: str, nonce: str, ts: int) -> str:
    """Sign a PoP message using Ed25519.
    
    Message format: "ticket_id|aud|nonce|ts" (utf-8 bytes)
    separator is '|' to avoid ambiguity.
    """
    private_bytes = bytes.fromhex(private_key_hex)
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_bytes)

    # Canonical message format
    message = f"{ticket_id}|{aud}|{nonce}|{ts}".encode("utf-8")
    
    signature = private_key.sign(message)
    return signature.hex()


def redeem_ticket(
    as_uri: str,
    ticket_id: str,
    pubkey: str,
    aud: str,
    pop_signature: str,
    nonce: str,
    ts: int,
) -> dict:
    """Redeem a ticket at the AS (Control Plane).

    In production: HTTP POST to as_uri/tickets/redeem.
    """
    print(f"[RP] Redeeming ticket at {as_uri}")
    print(f"      ticket_id: {ticket_id}")
    print(f"      aud: {aud}")
    print(f"      nonce: {nonce}")

    # Simulated response
    return {
        "token": "simulated-token-" + secrets.token_hex(8),
        "receipt": {
            "receipt_id": "rcpt-" + secrets.token_urlsafe(8),
            "path": "/proxion-keyring/receipts/rcpt-xxx.jsonld",
        },
    }


def fetch_connection_material(rs_uri: str, token: str) -> dict:
    """Fetch connection material from RS.

    In production: HTTP POST to rs_uri/bootstrap with token.
    """
    print(f"[RP] Fetching connection material from {rs_uri}")

    # Simulated proxion-keyringConnectionMaterial
    return {
        "type": "proxion-keyringConnectionMaterial",
        "dp": "wireguard",
        "interface": "wg0",
        "client": {"address": "10.0.0.2/32", "dns": ["10.0.0.1"]},
        "server": {"endpoint": "example.com:51820", "pubkey": secrets.token_hex(32)},
        "allowed_ips": ["10.0.0.0/24"],
        "expires_at": int(time.time()) + 3600,
    }


def generate_wg_config(material: dict) -> str:
    """Generate a WireGuard config from connection material."""
    client = material.get("client", {})
    server = material.get("server", {})
    allowed = material.get("allowed_ips", [])

    config = f"""[Interface]
Address = {client.get('address', '10.0.0.2/32')}
DNS = {', '.join(client.get('dns', []))}
PrivateKey = <YOUR_PRIVATE_KEY>

[Peer]
PublicKey = {server.get('pubkey', '')}
Endpoint = {server.get('endpoint', '')}
AllowedIPs = {', '.join(allowed)}
PersistentKeepalive = 25
"""
    return config


def main():
    parser = argparse.ArgumentParser(
        description="proxion-keyring Device RP CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --as-uri https://proxion-keyring.example/cp --pt abc123
  python cli.py --as-uri https://proxion-keyring.example/cp --pt abc123 --rs-uri https://rs.example
        """,
    )
    parser.add_argument("--as-uri", required=True, help="Authorization Server (CP) URI")
    parser.add_argument("--pt", required=True, help="Permission Ticket from QR code")
    parser.add_argument("--rs-uri", default="https://rs.proxion-keyring.example", help="Resource Server URI")
    parser.add_argument("--aud", default="wg0", help="Audience (RS interface)")
    parser.add_argument("--output", "-o", default=None, help="Output file for WireGuard config")

    args = parser.parse_args()

    # Generate device keypair
    pubkey, privkey = generate_keypair()
    print(f"[RP] Generated device keypair")
    print(f"      pubkey: {pubkey[:16]}...")

    # Generate PoP
    nonce = secrets.token_urlsafe(16)
    ts = int(time.time())
    pop_sig = sign_pop(privkey, args.pt, args.aud, nonce, ts)

    # Redeem ticket
    result = redeem_ticket(
        as_uri=args.as_uri,
        ticket_id=args.pt,
        pubkey=pubkey,
        aud=args.aud,
        pop_signature=pop_sig,
        nonce=nonce,
        ts=ts,
    )
    token = result.get("token")
    if not token:
        print("[RP] Error: No token received")
        sys.exit(1)

    print(f"[RP] Received token: {token[:20]}...")
    print(f"[RP] Receipt path: {result.get('receipt', {}).get('path')}")

    # Fetch connection material
    material = fetch_connection_material(args.rs_uri, token)
    print(f"[RP] Received connection material for {material.get('dp')}")

    # Generate WireGuard config
    wg_config = generate_wg_config(material)

    if args.output:
        with open(args.output, "w") as f:
            f.write(wg_config)
        print(f"[RP] Wrote config to {args.output}")
    else:
        print("\n--- WireGuard Config ---")
        print(wg_config)
        print("--- End Config ---")


if __name__ == "__main__":
    main()
