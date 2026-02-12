import logging
import json
import uuid
import os
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

from proxion_core.federation import Capability, FederationInvite, InviteAcceptance, RelationshipCertificate
from proxion_keyring.core.identity import Identity
from proxion_keyring.core.vault import VaultManager

class SharingManager:
    """Manages the decentralized sharing handshake and certificate lifecycle."""
    
    def __init__(self, identity: Identity, vault: VaultManager, vault_path: str):
        self.identity = identity
        self.vault = vault
        self.vault_path = vault_path
        self.pending_invites: Dict[str, FederationInvite] = {}

    def create_invite(self, recipient_web_id: str, resource_uri: str, actions: str = "read") -> Dict:
        """
        Step 1: Generate a signed invitation for a specific recipient.
        """
        # Mocking WebID to PubKey resolution for now
        recipient_pubkey = f"mock_pubkey_for_{recipient_web_id.split('/')[-1]}"
        
        cap = Capability(with_=resource_uri, can=actions)
        
        invite = FederationInvite(
            issuer={
                "public_key": self.identity.get_public_key_hex(),
                "did": f"did:proxion:{self.identity.get_public_key_hex()}"
            },
            endpoint_hints=["https://relay.proxion.tech/"], # Placeholder relay
            capabilities=[cap]
        )
        
        invite.sign(self.identity.private_key)
        self.pending_invites[invite.invitation_id] = invite
        
        logging.info(f"Created sharing invite {invite.invitation_id} for {recipient_web_id}")
        return invite.to_dict()

    def process_acceptance(self, acceptance_data: Dict) -> Dict:
        """
        Step 2: Verify the recipient's acceptance and issue the final RelationshipCertificate.
        """
        try:
            invite_id = acceptance_data.get("invitation_id")
            if invite_id not in self.pending_invites:
                raise ValueError("Unknown or expired invitation ID")
            
            invite = self.pending_invites[invite_id]
            
            # Issue the RelationshipCertificate
            cert = RelationshipCertificate(
                issuer=self.identity.get_public_key_hex(),
                subject=acceptance_data["responder"]["public_key"],
                capabilities=invite.capabilities,
                wireguard={
                    "internal_ip": "10.0.0.5/32", 
                    "allowed_ips": ["10.0.0.5/32"]
                }
            )
            
            cert.sign(self.identity.private_key)
            
            # Persist to ZK-Vault
            self._save_certificate(cert)
            
            # Cleanup
            del self.pending_invites[invite_id]
            
            logging.info(f"Successfully finalized sharing relationship with {cert.subject}")
            return cert.to_dict()
            
        except Exception as e:
            logging.error(f"Failed to process acceptance: {e}")
            raise

    def _save_certificate(self, cert: RelationshipCertificate):
        """Persists the certificate to the local relationship registry via the Vault."""
        # Load existing registry from Vault
        registry = self.vault.secure_load(self.vault_path, "relationships.json") or {}
        
        # Add new certificate
        registry[cert.certificate_id] = cert.to_dict()
        
        # Save back to Vault (Blinded & Encrypted)
        self.vault.secure_save(self.vault_path, "relationships.json", registry)
        logging.info(f"Saved relationship certificate {cert.certificate_id} to ZK-Vault")
