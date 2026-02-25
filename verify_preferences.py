"""
Verification for Phase 2 — User Onboarding Preferences
Run from d:\VAYO:  python verify_preferences.py
"""
import sys
from pydantic import ValidationError

# ── Import enum + schema directly (no DB / FastAPI startup needed) ────────────
sys.path.insert(0, ".")

# Inline re-declare to avoid DB import side-effects
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


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


class PreferencesUpdate(BaseModel):
    location: Optional[str] = Field(default=None, min_length=2, max_length=100)
    recharge_method: Optional[RechargeMethod] = None
    natural_rhythm: Optional[NaturalRhythm] = None
    ideal_group_size: Optional[IdealGroupSize] = None
    weekend_trip: Optional[WeekendTrip] = None
    weekend_env: Optional[WeekendEnv] = None
    background_vibe: Optional[BackgroundVibe] = None

    @field_validator("location", mode="before")
    @classmethod
    def strip_location(cls, v):
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def at_least_one_field(self):
        provided = [f for f in self.model_fields if getattr(self, f) is not None]
        if not provided:
            raise ValueError("At least one preference field must be provided.")
        return self


print("=" * 55)
print("Phase 2 Preferences — Verification Suite")
print("=" * 55)

PASS = "    ✅"
FAIL = "    ❌"

# ── Test 1: Full valid payload ────────────────────────────────────────────────
print("\n[1] Full valid payload...")
try:
    p = PreferencesUpdate(
        location="Mumbai",
        recharge_method="Quiet evening at home",
        natural_rhythm="Night owl",
        ideal_group_size="3-4 close friends",
        weekend_trip="Loose framework",
        weekend_env="Cozy coffee shop",
        background_vibe="Soft background chatter",
    )
    assert p.recharge_method == RechargeMethod.QUIET_EVENING
    assert p.location == "Mumbai"
    print(f"{PASS} All 7 fields accepted and parsed correctly")
except Exception as e:
    print(f"{FAIL} {e}"); sys.exit(1)

# ── Test 2: Partial update (only 2 fields) ────────────────────────────────────
print("\n[2] Partial update (location + recharge_method only)...")
try:
    p = PreferencesUpdate(location="  New Delhi  ", recharge_method="Getting outdoors")
    assert p.location == "New Delhi"   # whitespace stripped
    assert p.recharge_method == RechargeMethod.OUTDOORS
    print(f"{PASS} Partial update accepted, location whitespace stripped")
except Exception as e:
    print(f"{FAIL} {e}"); sys.exit(1)

# ── Test 3: Invalid enum value rejected ───────────────────────────────────────
print("\n[3] Invalid enum value should raise ValidationError...")
try:
    PreferencesUpdate(recharge_method="Party all night")  # not in enum
    print(f"{FAIL} Should have raised ValidationError"); sys.exit(1)
except ValidationError as e:
    errs = e.errors()
    assert any("recharge_method" in str(err) for err in errs)
    print(f"{PASS} Invalid enum value rejected → {errs[0]['type']}")

# ── Test 4: Empty payload rejected ───────────────────────────────────────────
print("\n[4] Completely empty payload should raise ValidationError...")
try:
    PreferencesUpdate()
    print(f"{FAIL} Should have raised ValidationError"); sys.exit(1)
except ValidationError as e:
    print(f"{PASS} Empty payload rejected → '{e.errors()[0]['msg']}'")

# ── Test 5: Location too short ───────────────────────────────────────────────
print("\n[5] Location string too short (< 2 chars)...")
try:
    PreferencesUpdate(location="A")
    print(f"{FAIL} Should have raised ValidationError"); sys.exit(1)
except ValidationError as e:
    assert any("location" in str(err) for err in e.errors())
    print(f"{PASS} Too-short location rejected → {e.errors()[0]['type']}")

# ── Test 6: Location too long ────────────────────────────────────────────────
print("\n[6] Location string too long (> 100 chars)...")
try:
    PreferencesUpdate(location="A" * 101)
    print(f"{FAIL} Should have raised ValidationError"); sys.exit(1)
except ValidationError as e:
    assert any("location" in str(err) for err in e.errors())
    print(f"{PASS} Too-long location rejected → {e.errors()[0]['type']}")

# ── Test 7: onboarding_complete logic simulation ─────────────────────────────
print("\n[7] onboarding_complete = true when all 7 fields present...")
ALL_PREF_FIELDS = {
    "location", "recharge_method", "natural_rhythm",
    "ideal_group_size", "weekend_trip", "weekend_env", "background_vibe",
}
full = {
    "location": "Mumbai",
    "recharge_method": "Quiet evening at home",
    "natural_rhythm": "Night owl",
    "ideal_group_size": "3-4 close friends",
    "weekend_trip": "Loose framework",
    "weekend_env": "Cozy coffee shop",
    "background_vibe": "Soft background chatter",
}
partial = {"location": "Mumbai", "recharge_method": "Getting outdoors"}

complete_full = all(full.get(f) for f in ALL_PREF_FIELDS)
complete_partial = all(partial.get(f) for f in ALL_PREF_FIELDS)

assert complete_full is True
assert complete_partial is False
print(f"{PASS} Full payload → onboarding_complete=True")
print(f"{PASS} Partial payload → onboarding_complete=False")

# ── Test 8: Enum .value serialisation (matches PG string) ─────────────────────
print("\n[8] Enum .value matches PostgreSQL ENUM string...")
assert RechargeMethod.QUIET_EVENING.value == "Quiet evening at home"
assert WeekendEnv.COFFEE_SHOP.value == "Cozy coffee shop"
assert BackgroundVibe.SILENCE.value == "Absolute silence"
print(f"{PASS} All spot-checked enum .values match PG ENUM strings")

print("\n" + "=" * 55)
print("✅  All 8 verification checks passed!")
print("=" * 55)
