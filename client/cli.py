import argparse
import sys
import logging
import platform
import os
from client.identity import IdentityManager
from client.orch import Orchestrator
from client.configurator import get_configurator

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("kleitikon")

DEFAULT_CP_URL = os.environ.get("VITE_CP_BASE_URL", "http://localhost:8787")
DEFAULT_RS_URL = os.environ.get("VITE_RS_BASE_URL", "http://localhost:8788")
DEFAULT_WEBID = "https://localhost:3200/alice/profile/card#me" # Placeholder for MVP

def cmd_connect(args):
    """Handle connect command."""
    logger.info("Initializing Kleitikon Client...")
    
    # 1. Identity
    id_mgr = IdentityManager()
    priv_key = id_mgr.get_identity()
    pub_key_hex = id_mgr.get_public_key_hex(priv_key)
    logger.info(f"Device Identity: {pub_key_hex[:16]}...")
    
    # 2. Orchestrator
    orch = Orchestrator(args.cp, args.rs)
    
    # 3. Redeem Ticket
    logger.info(f"Redeeming ticket: {args.ticket}")
    try:
        # For Phase 3, we pass empty policies unless specified?
        # Actually, in live E2E we fetched from Solid. 
        # The CLI should probably ideally accept a policy URL or file?
        # For this MVP step, let's assume the CP applies default policy if none provided 
        # OR we fetch the standard test policy if --dev-mode is used.
        
        policies = [] 
        # TODO: Implement policy fetching logic in CLI (Scope drift? Keep simple for now)
        
        if args.dev_policy:
             # Dev convenience
             policies = [{
                 "@context": "https://proxion.protocol/ontology/v1#",
                 "@type": "Policy",
                 "applies_to": { "all_devices": True },
                 "permits": [{ "action": "bootstrap", "resource": "*" }]
             }]
             logger.info("Using DEV policy payload.")
             
        token, receipt = orch.redeem_ticket(
            ticket_id=args.ticket,
            identity_key=priv_key,
            webid=args.webid,
            policies=policies,
            aud=args.aud
        )
        logger.info(f"Ticket Redeemed. Token: {token[:16]}...")
        if "id" in receipt:
            logger.info(f"Receipt ID: {receipt['id']}")
            
    except Exception as e:
        logger.error(f"Redemption Failed: {e}")
        sys.exit(1)
        
    # 4. Bootstrap (Get Config)
    logger.info("Bootstrapping WireGuard Tunnel...")
    try:
        wg_config = orch.bootstrap_tunnel(token, priv_key)
        logger.info("Received WireGuard Configuration.")
    except Exception as e:
        logger.error(f"Bootstrap Failed: {e}")
        sys.exit(1)
        
    # 5. Configurator (Apply)
    if args.dry_run:
        print("\n--- Dry Run: Generated Config ---\n")
        print(wg_config)
        print("\n---------------------------------")
        return

    logger.info(f"Applying configuration to interface '{args.interface}'...")
    try:
        configurator = get_configurator()
        configurator.apply_config(args.interface, wg_config)
        logger.info("Tunnel Active! 🚀")
    except Exception as e:
        logger.error(f"Configuration Failed: {e}")
        # Suggest admin if likely cause
        if platform.system() == "Windows" and "Run as Administrator" not in str(e):
             logger.warning("Hint: Make sure you are running as Administrator (for wg.exe).")
        sys.exit(1)

def cmd_status(args):
    """Handle status command."""
    id_mgr = IdentityManager()
    if not id_mgr.identity_file.exists():
        print("No identity found.")
        return

    priv_key = id_mgr.get_identity()
    pub_key = id_mgr.get_public_key_hex(priv_key)
    print(f"Device Identity: {pub_key}")
    print(f"Storage Path:    {id_mgr.storage_dir}")
    
    # TODO: Check running tunnel status via Configurator?

def main():
    parser = argparse.ArgumentParser(description="Kleitikon VPN Client")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Connect
    p_connect = subparsers.add_parser("connect", help="Redeem ticket and connect")
    p_connect.add_argument("--ticket", "-t", required=True, help="Ticket ID to redeem")
    p_connect.add_argument("--cp", default=DEFAULT_CP_URL, help=f"Control Plane URL (default: {DEFAULT_CP_URL})")
    p_connect.add_argument("--rs", default=DEFAULT_RS_URL, help=f"Resource Server URL (default: {DEFAULT_RS_URL})")
    p_connect.add_argument("--webid", default=DEFAULT_WEBID, help=f"User WebID (default: {DEFAULT_WEBID})")
    p_connect.add_argument("--aud", default="wg0", help="Audience/Interface (default: wg0)")
    p_connect.add_argument("--interface", "-i", default="wg0", help="Local WireGuard Interface Name")
    p_connect.add_argument("--dry-run", action="store_true", help="Print config and exit without applying")
    p_connect.add_argument("--dev-policy", action="store_true", help="Inject default permit policy (Dev Mode)")
    p_connect.set_defaults(func=cmd_connect)
    
    # Status
    p_status = subparsers.add_parser("status", help="Show client status")
    p_status.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
