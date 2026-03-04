"""
Standalone Auth Demo Server
----------------------------
Proves the Clerk authentication round-trip works without needing
PostgreSQL, Redis, Celery, or Pinecone running.

Run:   python auth_demo_server.py
Open:  http://localhost:8000
"""
import os
import time
import logging
from typing import Optional

import httpx
import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from dotenv import load_dotenv

# Load env vars from matching_system/.env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "matching_system", ".env"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL", "")
CLERK_AUDIENCE = os.getenv("CLERK_AUDIENCE") or None
JWKS_CACHE_TTL = 3600  # 1 hour

# ─── JWKS Cache (same logic as dependencies.py) ──────────────────────────────
_jwks_cache = {"keys": None, "cached_at": 0.0}


async def _get_jwks_client() -> jwt.PyJWKClient:
    now = time.monotonic()
    if _jwks_cache["keys"] is None or (now - _jwks_cache["cached_at"]) > JWKS_CACHE_TTL:
        if not CLERK_JWKS_URL:
            raise RuntimeError("CLERK_JWKS_URL is not set in .env")
        logger.info("Fetching JWKS from %s", CLERK_JWKS_URL)
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(CLERK_JWKS_URL)
            resp.raise_for_status()
            jwks_data = resp.json()
        client_obj = jwt.PyJWKClient.__new__(jwt.PyJWKClient)
        client_obj.jwk_set_data = jwks_data
        client_obj.jwk_set = jwt.PyJWKSet.from_dict(jwks_data)
        _jwks_cache["keys"] = client_obj
        _jwks_cache["cached_at"] = now
        logger.info("JWKS loaded — %d key(s)", len(client_obj.jwk_set.keys))
    return _jwks_cache["keys"]


# ─── Auth Dependency ─────────────────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)
_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired token.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """Verify Clerk JWT and return decoded claims."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise _UNAUTH
    try:
        jwks = await _get_jwks_client()
        key = jwks.get_signing_key_from_jwt(creds.credentials)
        kwargs = {"algorithms": ["RS256"]}
        if CLERK_AUDIENCE:
            kwargs["audience"] = CLERK_AUDIENCE
        payload = jwt.decode(creds.credentials, key.key, **kwargs)
    except jwt.ExpiredSignatureError:
        raise _UNAUTH
    except jwt.DecodeError:
        raise _UNAUTH
    except Exception as exc:
        logger.exception("JWT verify error: %s", exc)
        raise _UNAUTH
    return payload  # return full claims so demo page can display them


# ─── FastAPI App ─────────────────────────────────────────────────────────────
app = FastAPI(title="Clerk Auth Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def serve_demo():
    """Serve the demo HTML page."""
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "matching_system", "static", "auth_demo.html")
    )


@app.get("/api/v1/health")
async def health():
    """Public - no auth required."""
    return {"status": "healthy", "auth": "clerk", "jwks_url": CLERK_JWKS_URL}


@app.get("/api/v1/users/me")
async def get_me(claims: dict = Depends(get_current_user)):
    """
    🔒 PROTECTED — requires a valid Clerk JWT.
    Returns the authenticated user's decoded token claims.
    """
    return {
        "authenticated": True,
        "clerk_user_id": claims.get("sub"),
        "session_id": claims.get("sid"),
        "issued_at": claims.get("iat"),
        "expires_at": claims.get("exp"),
        "azp": claims.get("azp"),
        "all_claims": claims,
    }


if __name__ == "__main__":
    import uvicorn
    print("\n🚀  Auth Demo Server starting at http://localhost:8000")
    print("    Open your browser to test the Clerk sign-in flow\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
