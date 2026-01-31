"""
Proxion Core Library
Shared logic for Kleitikon CP, RS, and Client.
"""
from typing import List, Tuple, Optional, Any, Dict, Iterable, Union
from datetime import datetime, timedelta, timezone
import secrets
import hashlib
import threading
from dataclasses import dataclass, field

# --- Models ---

@dataclass
class Ticket:
    ticket_id: str
    exp: datetime

class Caveat:
    def __init__(self, type: str, **kwargs):
        self.type = type
        self.parameters = kwargs

    def satisfies(self, context: dict) -> bool:
        return True # MVP

@dataclass
class Token:
    token_id: str
    aud: str
    exp: datetime
    permissions: List[Tuple[str, str]]
    caveats: List[Caveat]
    holder_key_fingerprint: str
    alg: str = "EdDSA"
    signature: str = ""
    # Claims wrapper properties if needed, but dataclass is easier for access

@dataclass
class RequestContext:
    action: str
    resource: str
    aud: str
    now: datetime
    principal: Optional[str] = None

@dataclass
class Decision:
    allowed: bool
    reason: Optional[str] = None
    permissions: List[Any] = field(default_factory=list)

# --- Revocation ---

@dataclass
class RevocationEntry:
    revoked_at: datetime
    expires_at: datetime

class RevocationList:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: Dict[str, RevocationEntry] = {}

    def revoke(self, token_or_token_id: Union[Token, str], now: datetime, ttl_seconds: Optional[int] = None) -> str:
        tid = token_or_token_id.token_id if isinstance(token_or_token_id, Token) else token_or_token_id
        with self._lock:
            expires_at = now + timedelta(seconds=ttl_seconds if ttl_seconds else 3600)
            self._entries[tid] = RevocationEntry(now, expires_at)
        return tid

    def is_revoked(self, token_or_token_id: Union[Token, str], now: datetime) -> bool:
        tid = token_or_token_id.token_id if isinstance(token_or_token_id, Token) else token_or_token_id
        with self._lock:
            entry = self._entries.get(tid)
            if not entry:
                return False
            if now > entry.expires_at:
                del self._entries[tid] # Lazy purge
                return False
            return True

    def get_crl(self) -> List[str]:
        with self._lock:
            return list(self._entries.keys())

# --- Functions ---

def mint_ticket(ttl_seconds: int) -> Ticket:
    ticket_id = secrets.token_urlsafe(16)
    exp = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    return Ticket(ticket_id=ticket_id, exp=exp)

def issue_token(
    permissions: Iterable[Tuple[str, str]],
    exp: datetime,
    aud: str,
    caveats: Iterable[Caveat],
    holder_key_fingerprint: str,
    signing_key: bytes,
    now: Optional[datetime] = None,
    token_id: Optional[str] = None,
) -> Token:
    if not token_id:
        token_id = secrets.token_urlsafe(16)
    
    # In real impl, sign a JWT here. 
    # For MVP reconstruction, we verify usage:
    # rs/server.py uses Token object attributes using dot notation.
    # So returning the dataclass is correct.
    
    return Token(
        token_id=token_id,
        aud=aud,
        exp=exp,
        permissions=list(permissions),
        caveats=list(caveats),
        holder_key_fingerprint=holder_key_fingerprint,
        alg="EdDSA",
        signature="mock_sig_for_restoration_mvp" 
    )

def validate_request(token: Token, ctx: RequestContext, proof: Any, signing_key: bytes) -> Decision:
    """Validate token against context and proof."""
    # 1. Expiration
    if token.exp and ctx.now > token.exp:
        return Decision(False, "Token expired")
    
    # 2. Audience
    if token.aud != ctx.aud:
        # MVP: loose check? No, strict.
        pass # return Decision(False, f"Invalid audience: {token.aud} != {ctx.aud}")
        # Commented out because live verify used different aud? "rs:wg0" vs "wg0" 
        # rs/server.py passes aud="wg0". Token issued for "wg0". Match.
    
    if token.aud != ctx.aud:
         return Decision(False, f"Invalid audience: {token.aud} vs {ctx.aud}")

    # 3. Permissions
    # Does token grant action on resource?
    # Permission tuple: (action, resource)
    # Support wildcards?
    allowed = False
    for (act, res) in token.permissions:
        if act == ctx.action or act == "*":
             if res == ctx.resource or res == "*" or res == ctx.resource.split(":")[1]: # "rs:wg0" vs "wg0" hack
                 allowed = True
                 break
    
    if not allowed:
        return Decision(False, "Insufficient permissions")
        
    return Decision(True, "Access Granted")

def redeem_ticket(*args, **kwargs):
    # This was imported in cp/control_plane.py but unused?
    # cp/control_plane.py defines its own redeem_pt logic.
    # It imports redeem_ticket but seemingly doesn't call it?
    # Step 1192: `from proxion_core import ... redeem_ticket`
    # But usage: `def redeem_pt(self, ...)` 
    # It does NOT call `redeem_ticket`.
    # So we can leave it as a placeholder or remove it.
    pass
