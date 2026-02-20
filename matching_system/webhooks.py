"""
Clerk Webhook Handler
----------------------
POST /webhooks/clerk

Verifies incoming Clerk webhook events using the svix library,
then syncs user data to our PostgreSQL users table.

Supported events:
  - user.created  → upsert user row
  - user.updated  → upsert user row
  - user.deleted  → soft-delete (is_active = false)
"""
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from svix.webhooks import Webhook, WebhookVerificationError

from .database import db_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")


# ---------------------------------------------------------------------------
# Pydantic Schemas — parse Clerk's JSON payload
# ---------------------------------------------------------------------------


class ClerkEmailAddress(BaseModel):
    """Single email entry inside Clerk's user.created/updated payload."""
    email_address: str
    id: str


class ClerkUserPayload(BaseModel):
    """Data block for user.created and user.updated events."""
    id: str                                              # Clerk user ID (user_xxx)
    email_addresses: List[ClerkEmailAddress] = Field(default_factory=list)
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    public_metadata: Dict[str, Any] = Field(default_factory=dict)


class ClerkDeletedPayload(BaseModel):
    """Data block for user.deleted events."""
    id: str
    deleted: bool = True


class ClerkWebhookEvent(BaseModel):
    """Top-level Clerk webhook envelope."""
    type: str
    data: Dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _primary_email(payload: ClerkUserPayload) -> Optional[str]:
    """Return the first email address, or None if not present."""
    if payload.email_addresses:
        return payload.email_addresses[0].email_address
    return None


async def _upsert_user(payload: ClerkUserPayload) -> None:
    """
    Insert or update a user row in PostgreSQL.
    Uses ON CONFLICT (user_id) DO UPDATE to handle both created & updated.
    """
    email = _primary_email(payload)
    import json

    query = """
        INSERT INTO users (
            user_id, email, first_name, last_name, public_metadata, is_active
        ) VALUES ($1, $2, $3, $4, $5::jsonb, true)
        ON CONFLICT (user_id) DO UPDATE SET
            email           = EXCLUDED.email,
            first_name      = EXCLUDED.first_name,
            last_name       = EXCLUDED.last_name,
            public_metadata = EXCLUDED.public_metadata,
            is_active       = true;
    """
    async with db_manager.pg_pool.acquire() as conn:
        await conn.execute(
            query,
            payload.id,
            email,
            payload.first_name,
            payload.last_name,
            json.dumps(payload.public_metadata),
        )
    logger.info("Upserted user %s (%s)", payload.id, email)


async def _soft_delete_user(clerk_id: str) -> None:
    """Mark a user as inactive instead of hard-deleting."""
    query = "UPDATE users SET is_active = false WHERE user_id = $1;"
    async with db_manager.pg_pool.acquire() as conn:
        result = await conn.execute(query, clerk_id)
    logger.info("Soft-deleted user %s — pg result: %s", clerk_id, result)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/clerk", status_code=status.HTTP_200_OK)
async def clerk_webhook(
    request: Request,
    svix_id: Optional[str] = Header(None, alias="svix-id"),
    svix_timestamp: Optional[str] = Header(None, alias="svix-timestamp"),
    svix_signature: Optional[str] = Header(None, alias="svix-signature"),
) -> Dict[str, str]:
    """
    Receives and processes Clerk webhook events.

    Security: All requests without a valid svix signature are rejected with
    HTTP 400 (not 401 / not 200 — this is a hard security boundary, not a
    transient error Clerk should retry).

    All downstream DB errors return HTTP 200 with a logged warning so Clerk
    does not retry unnecessarily (idempotent upserts are safe to replay anyway).
    """
    # ---- 1. Svix header presence check ------------------------------------
    if not all([svix_id, svix_timestamp, svix_signature]):
        logger.warning("Clerk webhook received with missing svix headers")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required svix signature headers.",
        )

    # ---- 2. Signature verification ----------------------------------------
    if not WEBHOOK_SECRET:
        logger.error("WEBHOOK_SECRET env var is not set — cannot verify webhook")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured.",
        )

    raw_body: bytes = await request.body()
    headers = {
        "svix-id": svix_id,
        "svix-timestamp": svix_timestamp,
        "svix-signature": svix_signature,
    }

    try:
        wh = Webhook(WEBHOOK_SECRET)
        wh.verify(raw_body, headers)
    except WebhookVerificationError as exc:
        logger.warning("Clerk webhook signature verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature.",
        )

    # ---- 3. Parse envelope ------------------------------------------------
    try:
        event = ClerkWebhookEvent.model_validate_json(raw_body)
    except Exception as exc:
        logger.warning("Failed to parse Clerk webhook payload: %s", exc)
        # Return 200 to avoid Clerk retrying a malformed payload loop
        return {"status": "ignored", "reason": "unparseable payload"}

    logger.info("Received Clerk webhook event: %s", event.type)

    # ---- 4. Route event ---------------------------------------------------
    try:
        if event.type in ("user.created", "user.updated"):
            user_payload = ClerkUserPayload.model_validate(event.data)
            await _upsert_user(user_payload)

        elif event.type == "user.deleted":
            deleted_payload = ClerkDeletedPayload.model_validate(event.data)
            await _soft_delete_user(deleted_payload.id)

        else:
            logger.info("Unhandled Clerk event type '%s' — ignoring", event.type)
            return {"status": "ignored", "event_type": event.type}

    except Exception as exc:
        # Log but return 200 so Clerk doesn't retry — upserts are idempotent
        logger.exception(
            "DB sync failed for Clerk event '%s': %s", event.type, exc
        )
        return {"status": "error", "detail": "Internal sync failed — check server logs"}

    return {"status": "ok", "event_type": event.type}
