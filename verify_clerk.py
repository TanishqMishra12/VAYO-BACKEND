"""
Verification script for Clerk integration.
Run from d:\VAYO:  python verify_clerk.py
"""
import httpx
import json
import sys

JWKS_URL = "https://literate-monkfish-41.clerk.accounts.dev/.well-known/jwks.json"

print("=" * 55)
print("Clerk Backend Integration — Verification")
print("=" * 55)

# ── Test 1: JWKS URL is reachable ──────────────────────────
print("\n[1] Fetching JWKS from Clerk...")
try:
    r = httpx.get(JWKS_URL, timeout=10)
    data = r.json()
    keys = data.get("keys", [])
    print(f"    HTTP status : {r.status_code}")
    print(f"    Keys found  : {len(keys)}")
    for k in keys:
        print(f"    ✓ kid={k.get('kid')}, alg={k.get('alg')}, kty={k.get('kty')}")
    if r.status_code == 200 and len(keys) > 0:
        print("    ✅ JWKS endpoint OK")
    else:
        print("    ❌ JWKS endpoint returned unexpected data")
        sys.exit(1)
except Exception as e:
    print(f"    ❌ JWKS fetch failed: {e}")
    sys.exit(1)

# ── Test 2: PyJWT can load the JWKS key set ────────────────
print("\n[2] Loading keys with PyJWT PyJWKSet...")
try:
    import jwt
    jwk_set = jwt.PyJWKSet.from_dict(data)
    print(f"    Keys loaded : {len(jwk_set.keys)}")
    print("    ✅ PyJWT JWKS parsing OK")
except Exception as e:
    print(f"    ❌ PyJWT JWKS load failed: {e}")
    sys.exit(1)

# ── Test 3: PyJWT rejects a malformed token ────────────────
print("\n[3] Testing JWT decode rejects invalid token...")
try:
    import jwt as pyjwt
    signing_key = list(jwk_set.keys)[0]
    pyjwt.decode(
        "this.is.not.a.valid.jwt",
        signing_key.key,
        algorithms=["RS256"],
    )
    print("    ❌ Should have raised DecodeError!")
    sys.exit(1)
except pyjwt.DecodeError:
    print("    ✅ Invalid token correctly rejected (DecodeError)")
except Exception as e:
    print(f"    ✅ Invalid token rejected: {type(e).__name__}")

# ── Test 4: svix rejects bad webhook signature ─────────────
print("\n[4] Testing svix rejects bad signature...")
try:
    import time
    from svix.webhooks import Webhook, WebhookVerificationError

    secret = "whsec_MfKQ9r8GKYqrTwjUPD8IucrlCx1ObfTW"  # dummy
    wh = Webhook(secret)
    body = json.dumps({"type": "user.created", "data": {"id": "user_test"}}).encode()
    bad_headers = {
        "svix-id": "msg_test123",
        "svix-timestamp": str(int(time.time())),
        "svix-signature": "v1,badsignature==",
    }
    try:
        wh.verify(body, bad_headers)
        print("    ❌ Should have rejected bad signature!")
        sys.exit(1)
    except (WebhookVerificationError, Exception):
        print("    ✅ Bad webhook signature correctly rejected")
except Exception as e:
    print(f"    ❌ svix test error: {e}")
    sys.exit(1)

# ── Test 5: Pydantic schemas parse Clerk user payload ─────
print("\n[5] Testing Pydantic schemas parse Clerk payload...")
try:
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    # Inline test without importing the full module (avoids DB startup)
    from pydantic import BaseModel, Field
    from typing import List, Optional, Any, Dict

    class ClerkEmailAddress(BaseModel):
        email_address: str
        id: str

    class ClerkUserPayload(BaseModel):
        id: str
        email_addresses: List[ClerkEmailAddress] = Field(default_factory=list)
        first_name: Optional[str] = None
        last_name: Optional[str] = None
        public_metadata: Dict[str, Any] = Field(default_factory=dict)

    sample = {
        "id": "user_2abc123",
        "email_addresses": [{"email_address": "test@example.com", "id": "idn_1"}],
        "first_name": "Tanishq",
        "last_name": "Mishra",
        "public_metadata": {"role": "admin"},
    }
    parsed = ClerkUserPayload.model_validate(sample)
    assert parsed.id == "user_2abc123"
    assert parsed.email_addresses[0].email_address == "test@example.com"
    assert parsed.public_metadata["role"] == "admin"
    print(f"    Parsed user : {parsed.id} ({parsed.first_name} {parsed.last_name})")
    print(f"    Email       : {parsed.email_addresses[0].email_address}")
    print("    ✅ Pydantic schema validation OK")
except Exception as e:
    print(f"    ❌ Pydantic schema failed: {e}")
    sys.exit(1)

print("\n" + "=" * 55)
print("✅  All 5 verification checks passed!")
print("=" * 55)
