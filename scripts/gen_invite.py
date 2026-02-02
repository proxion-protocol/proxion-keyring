import json
import time
from proxion_core.federation import FederationInvite, Capability
from proxion_keyring.identity import load_or_create_identity_key
from cryptography.hazmat.primitives import serialization

def main():
    key = load_or_create_identity_key()
    pub_hex = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    ).hex()
    
    cap = Capability(with_="stash://alice/test", can="read")
    invite = FederationInvite(
        issuer={"public_key": pub_hex, "did": f"did:key:{pub_hex}"},
        endpoint_hints=["udp://127.0.0.1:5000"],
        capabilities=[cap]
    )
    invite.sign(key)
    
    with open("invite.json", "w") as f:
        json.dump(invite.to_dict(), f, indent=2)
    print("invite.json created.")

if __name__ == "__main__":
    main()
