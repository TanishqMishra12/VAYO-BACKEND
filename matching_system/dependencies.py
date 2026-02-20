"""
Clerk JWT Authentication Dependency
------------------------------------
Provides `get_current_user` — a FastAPI dependency that:
  1. Parses the Authorization: Bearer <token> header
  2. Fetches and caches Clerk's JWKS (1-hour TTL)
  3. Decodes + verifies the JWT (RS256, exp, iat, azp)
  4. Returns the Clerk user_id (sub claim) or raises HTTP 401

Usage:
    from .dependencies import get_current_user

    @app.get("/api/v1/me")
    async def get_me(user_id: str = Depends(get_current_user)):
        return {"clerk_user_id": user_id}
"""
import logging
import os
import time
from typing import Optional

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CLERK_JWKS_URL: str = os.getenv(
    "CLERK_JWKS_URL", ""
)  # e.g. https://<clerk-domain>/.well-known/jwks.json
CLERK_AUDIENCE: Optional[str] = os.getenv("CLERK_AUDIENCE") or None  # azp claim (optional)
JWKS_CACHE_TTL_SECONDS: int = 3600  # Refresh public keys every hour

# ---------------------------------------------------------------------------
# JWKS In-Memory Cache
# ---------------------------------------------------------------------------
_jwks_cache: dict = {
    "keys": None,       # PyJWT JWKSClient (holds parsed keys)
    "cached_at": 0.0,   # epoch float
}


async def _get_jwks_client() -> jwt.PyJWKClient:
    """
    Returns a PyJWKClient whose keys are refreshed at most once per hour.
    Thread-safe for asyncio (single-threaded event loop).
    """
    now = time.monotonic()
    if _jwks_cache["keys"] is None or (now - _jwks_cache["cached_at"]) > JWKS_CACHE_TTL_SECONDS:
        if not CLERK_JWKS_URL:
            raise RuntimeError(
                "CLERK_JWKS_URL environment variable is not set. "
                "Get it from: Clerk Dashboard → API Keys → JWKS URL"
            )
        logger.info("Refreshing Clerk JWKS from %s", CLERK_JWKS_URL)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(CLERK_JWKS_URL)
            response.raise_for_status()
            jwks_data = response.json()

        # Build a PyJWKClient from the raw JWKS dict — select key by kid automatically
        jwks_client = jwt.PyJWKClient.__new__(jwt.PyJWKClient)
        jwks_client.jwk_set_data = jwks_data
        jwks_client.jwk_set = jwt.PyJWKSet.from_dict(jwks_data)

        _jwks_cache["keys"] = jwks_client
        _jwks_cache["cached_at"] = now
        logger.info("JWKS cache refreshed — %d key(s) loaded", len(jwks_client.jwk_set.keys))

    return _jwks_cache["keys"]


# ---------------------------------------------------------------------------
# Auth Dependency
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or expired authentication token.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> str:
    """
    FastAPI dependency — verifies the Clerk JWT and returns the Clerk user_id.

    Raises HTTP 401 if:
      - No Authorization header is present
      - Token is malformed, expired, or has an invalid signature
      - azp claim does not match CLERK_AUDIENCE (when CLERK_AUDIENCE is set)
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _CREDENTIALS_EXCEPTION

    token = credentials.credentials

    try:
        jwks_client = await _get_jwks_client()

        # Extract the signing key matching the token's kid header
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode options — PyJWT validates exp and iat automatically
        decode_options = {
            "verify_exp": True,
            "verify_iat": True,
        }

        # Build audience validation arguments
        decode_kwargs: dict = {
            "algorithms": ["RS256"],
            "options": decode_options,
        }

        # Optionally validate azp (Authorized Party) claim
        if CLERK_AUDIENCE:
            decode_kwargs["audience"] = CLERK_AUDIENCE

        payload: dict = jwt.decode(
            token,
            signing_key.key,
            **decode_kwargs,
        )

    except jwt.ExpiredSignatureError:
        logger.warning("Clerk JWT expired")
        raise _CREDENTIALS_EXCEPTION
    except jwt.InvalidAudienceError:
        logger.warning("Clerk JWT: invalid azp/audience claim")
        raise _CREDENTIALS_EXCEPTION
    except jwt.DecodeError as exc:
        logger.warning("Clerk JWT decode error: %s", exc)
        raise _CREDENTIALS_EXCEPTION
    except httpx.HTTPError as exc:
        # JWKS fetch failed — don't expose internal error to client
        logger.error("Failed to fetch Clerk JWKS: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable.",
        )
    except Exception as exc:
        logger.exception("Unexpected error during JWT verification: %s", exc)
        raise _CREDENTIALS_EXCEPTION

    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        logger.warning("Clerk JWT missing 'sub' claim")
        raise _CREDENTIALS_EXCEPTION

    return user_id


# ---------------------------------------------------------------------------
# Utility: invalidate JWKS cache (useful for testing)
# ---------------------------------------------------------------------------
def invalidate_jwks_cache() -> None:
    """Force the next request to re-fetch the JWKS from Clerk."""
    _jwks_cache["keys"] = None
    _jwks_cache["cached_at"] = 0.0
    logger.info("JWKS cache invalidated")
