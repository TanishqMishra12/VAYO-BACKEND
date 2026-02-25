"""
User Onboarding Preferences
-----------------------------
Provides:
  1. Python Enum classes (mirror PostgreSQL ENUM types — single source of truth)
  2. Pydantic v2 schemas (validation middleware — equivalent of Zod/Joi)
  3. PATCH /api/v1/users/{user_id}/preferences  (controller)

All enum values are strictly validated by Pydantic before the DB is touched.
PostgreSQL ENUMs add a second enforcement layer at the storage level.
"""
import json
import logging
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field, field_validator, model_validator

from .database import db_manager
from .dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["User Preferences"])


# =============================================================================
# 1. ENUM DEFINITIONS
#    Mirrors the PostgreSQL ENUM types in user_preferences_migration.sql.
#    Pydantic will reject any value not in these lists with a clear 422 error.
# =============================================================================


class RechargeMethod(str, Enum):
    HITTING_TOWN = "Hitting the town"
    QUIET_EVENING = "Quiet evening at home"
    SMALL_DINNER = "Small dinner with close friends"
    OUTDOORS = "Getting outdoors"


class NaturalRhythm(str, Enum):
    EARLY_BIRD = "Early bird"
    NIGHT_OWL = "Night owl"
    IN_BETWEEN = "Comfortably in between"


class IdealGroupSize(str, Enum):
    MORE_THE_MERRIER = "The more the merrier"
    CLOSE_FRIENDS = "3-4 close friends"
    ONE_OTHER = "Just me and one other"
    SOLO = "Riding solo"


class WeekendTrip(str, Enum):
    DETAILED = "Detailed itinerary"
    SPONTANEOUS = "Completely spontaneous"
    LOOSE = "Loose framework"


class WeekendEnv(str, Enum):
    CITY = "City streets and nightlife"
    CABIN = "Quiet cabin in the woods"
    BEACH = "Sunny beach or poolside"
    COFFEE_SHOP = "Cozy coffee shop"


class BackgroundVibe(str, Enum):
    LOUD = "Loud music and high energy"
    CHATTER = "Soft background chatter"
    SILENCE = "Absolute silence"


# =============================================================================
# 2. PYDANTIC SCHEMAS  (Validation Middleware — equivalent of Zod/Joi)
#    PreferencesUpdate: incoming PATCH body (all fields optional → partial update)
#    PreferencesResponse: outgoing response shape
# =============================================================================


class PreferencesUpdate(BaseModel):
    """
    PATCH /api/v1/users/{user_id}/preferences — request body.

    All fields are optional so clients can submit partial updates
    (e.g., only location + recharge_method on step 1 of a multi-step form).

    Pydantic automatically rejects:
      • Values not in the Enum set → HTTP 422 with a clear message listing valid choices
      • location strings outside 2–100 chars → HTTP 422
      • Completely empty payloads (enforced by model_validator below)
    """

    location: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=100,
        description="City or area the user is based in",
        examples=["Mumbai", "New York City"],
    )
    recharge_method: Optional[RechargeMethod] = Field(
        default=None,
        description="How the user prefers to spend evenings",
    )
    natural_rhythm: Optional[NaturalRhythm] = Field(
        default=None,
        description="User's natural daily rhythm",
    )
    ideal_group_size: Optional[IdealGroupSize] = Field(
        default=None,
        description="Preferred social group size",
    )
    weekend_trip: Optional[WeekendTrip] = Field(
        default=None,
        description="Weekend trip planning style",
    )
    weekend_env: Optional[WeekendEnv] = Field(
        default=None,
        description="Preferred weekend environment",
    )
    background_vibe: Optional[BackgroundVibe] = Field(
        default=None,
        description="Preferred ambient noise level",
    )

    @field_validator("location", mode="before")
    @classmethod
    def strip_location(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace before length validation."""
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def at_least_one_field(self) -> "PreferencesUpdate":
        """Reject a payload where every field is None (empty PATCH is useless)."""
        provided = [
            f for f in self.model_fields
            if getattr(self, f) is not None
        ]
        if not provided:
            raise ValueError(
                "At least one preference field must be provided in the request body."
            )
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "location": "Mumbai",
                "recharge_method": "Quiet evening at home",
                "natural_rhythm": "Night owl",
                "ideal_group_size": "3-4 close friends",
                "weekend_trip": "Loose framework",
                "weekend_env": "Cozy coffee shop",
                "background_vibe": "Soft background chatter",
            }
        }
    }


class PreferencesResponse(BaseModel):
    """Shape of the updated preferences returned after a successful PATCH."""

    user_id: str
    location: Optional[str] = None
    recharge_method: Optional[RechargeMethod] = None
    natural_rhythm: Optional[NaturalRhythm] = None
    ideal_group_size: Optional[IdealGroupSize] = None
    weekend_trip: Optional[WeekendTrip] = None
    weekend_env: Optional[WeekendEnv] = None
    background_vibe: Optional[BackgroundVibe] = None
    onboarding_complete: bool


# =============================================================================
# 3. CONTROLLER — PATCH /api/v1/users/{user_id}/preferences
# =============================================================================


@router.patch(
    "/{user_id}/preferences",
    response_model=PreferencesResponse,
    status_code=status.HTTP_200_OK,
    summary="Update user onboarding preferences",
    description=(
        "Partially updates a user's onboarding preferences. "
        "Only send the fields you want to change — omit the rest. "
        "Sets `onboarding_complete = true` once all 7 fields are filled in."
    ),
)
async def update_preferences(
    user_id: str = Path(..., description="The Clerk user ID (e.g. user_abc123)"),
    payload: PreferencesUpdate = None,
    current_user_id: str = Depends(get_current_user),
) -> PreferencesResponse:
    """
    PATCH /api/v1/users/{user_id}/preferences

    Security:  Users may only update their own preferences (403 otherwise).
    Upsert:    Creates a preferences row if one does not yet exist.
    Completion: Marks onboarding_complete = true when all 7 fields are non-null.
    Errors:    Returns structured JSON for 403, 404, and 500 cases.
    """
    # ── Authorization: users can only edit their own preferences ──────────────
    if current_user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update another user's preferences.",
        )

    # ── Guard: ensure the user exists in our users table ──────────────────────
    async with db_manager.pg_pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE user_id = $1 AND is_active = true;",
            user_id,
        )
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found.",
        )

    # ── Build dynamic SET clause from non-None payload fields ─────────────────
    # Convert enums to their .value strings for asyncpg (PG expects plain strings
    # which it then casts to the ENUM type via the column definition).
    updates: dict = {}
    for field_name in PreferencesUpdate.model_fields:
        val = getattr(payload, field_name)
        if val is not None:
            updates[field_name] = val.value if isinstance(val, Enum) else val

    # ── Upsert preferences row ─────────────────────────────────────────────────
    try:
        async with db_manager.pg_pool.acquire() as conn:
            # Fetch current state (to compute onboarding_complete)
            current = await conn.fetchrow(
                "SELECT * FROM user_preferences WHERE user_id = $1;", user_id
            )
            current_dict: dict = dict(current) if current else {}

            # Merge: current values + incoming updates
            merged = {**current_dict, **updates}

            # Mark onboarding complete when all 7 preference fields are present
            all_pref_fields = {
                "location", "recharge_method", "natural_rhythm",
                "ideal_group_size", "weekend_trip", "weekend_env", "background_vibe",
            }
            onboarding_complete: bool = all(
                merged.get(f) is not None for f in all_pref_fields
            )

            # Build parameterised INSERT … ON CONFLICT DO UPDATE
            columns = list(updates.keys()) + ["onboarding_complete"]
            values = list(updates.values()) + [onboarding_complete]

            # Param placeholders: $1=user_id, $2…$n=values
            placeholders = ", ".join(f"${i + 2}" for i in range(len(values)))
            col_list = ", ".join(columns)
            update_set = ", ".join(
                f"{col} = EXCLUDED.{col}" for col in columns
            )

            query = f"""
                INSERT INTO user_preferences (user_id, {col_list})
                VALUES ($1, {placeholders})
                ON CONFLICT (user_id) DO UPDATE
                SET {update_set};
            """
            await conn.execute(query, user_id, *values)

            # Fetch the freshly updated row to return
            updated_row = await conn.fetchrow(
                "SELECT * FROM user_preferences WHERE user_id = $1;", user_id
            )

    except Exception as exc:
        logger.exception("Failed to update preferences for user %s: %s", user_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save preferences. Please try again.",
        )

    row = dict(updated_row)

    return PreferencesResponse(
        user_id=row["user_id"],
        location=row.get("location"),
        recharge_method=row.get("recharge_method"),
        natural_rhythm=row.get("natural_rhythm"),
        ideal_group_size=row.get("ideal_group_size"),
        weekend_trip=row.get("weekend_trip"),
        weekend_env=row.get("weekend_env"),
        background_vibe=row.get("background_vibe"),
        onboarding_complete=row.get("onboarding_complete", False),
    )


# ─── Bonus: GET current preferences (read-only, no auth guard needed) ─────────

@router.get(
    "/{user_id}/preferences",
    response_model=PreferencesResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user onboarding preferences",
)
async def get_preferences(
    user_id: str = Path(..., description="The Clerk user ID"),
    current_user_id: str = Depends(get_current_user),
) -> PreferencesResponse:
    """GET /api/v1/users/{user_id}/preferences — returns current saved preferences."""
    if current_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")

    async with db_manager.pg_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM user_preferences WHERE user_id = $1;", user_id
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preferences found. Complete the onboarding questionnaire.",
        )

    row = dict(row)
    return PreferencesResponse(
        user_id=row["user_id"],
        location=row.get("location"),
        recharge_method=row.get("recharge_method"),
        natural_rhythm=row.get("natural_rhythm"),
        ideal_group_size=row.get("ideal_group_size"),
        weekend_trip=row.get("weekend_trip"),
        weekend_env=row.get("weekend_env"),
        background_vibe=row.get("background_vibe"),
        onboarding_complete=row.get("onboarding_complete", False),
    )
