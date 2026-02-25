-- =============================================================================
-- Phase 2: User Onboarding Preferences Migration
-- =============================================================================
-- Run ONCE after clerk_migration.sql:
--   psql -d community_matching -f matching_system/user_preferences_migration.sql
-- =============================================================================

BEGIN;

-- ─── 1. PostgreSQL ENUM Types ─────────────────────────────────────────────────
-- Each dropdown becomes a strongly-typed PG ENUM, preventing invalid rows
-- at the database level (constraint lives in PG, not just app code).

CREATE TYPE recharge_method_enum AS ENUM (
    'Hitting the town',
    'Quiet evening at home',
    'Small dinner with close friends',
    'Getting outdoors'
);

CREATE TYPE natural_rhythm_enum AS ENUM (
    'Early bird',
    'Night owl',
    'Comfortably in between'
);

CREATE TYPE ideal_group_size_enum AS ENUM (
    'The more the merrier',
    '3-4 close friends',
    'Just me and one other',
    'Riding solo'
);

CREATE TYPE weekend_trip_enum AS ENUM (
    'Detailed itinerary',
    'Completely spontaneous',
    'Loose framework'
);

CREATE TYPE weekend_env_enum AS ENUM (
    'City streets and nightlife',
    'Quiet cabin in the woods',
    'Sunny beach or poolside',
    'Cozy coffee shop'
);

CREATE TYPE background_vibe_enum AS ENUM (
    'Loud music and high energy',
    'Soft background chatter',
    'Absolute silence'
);

-- ─── 2. user_preferences Table ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id             TEXT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,

    -- Free-text location with length guard (enforced in app layer too)
    location            TEXT           CHECK (char_length(location) BETWEEN 2 AND 100),

    -- Enum columns — invalid values will raise a PG error at insert/update time
    recharge_method     recharge_method_enum,
    natural_rhythm      natural_rhythm_enum,
    ideal_group_size    ideal_group_size_enum,
    weekend_trip        weekend_trip_enum,
    weekend_env         weekend_env_enum,
    background_vibe     background_vibe_enum,

    -- Onboarding state tracking
    onboarding_complete BOOLEAN        DEFAULT false,

    created_at          TIMESTAMPTZ    DEFAULT NOW(),
    updated_at          TIMESTAMPTZ    DEFAULT NOW()
);

-- ─── 3. Auto-update updated_at on every PATCH ─────────────────────────────────
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_user_preferences_updated_at
BEFORE UPDATE ON user_preferences
FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ─── 4. Index for fast lookup by onboarding state (used by matching pipeline) ─
CREATE INDEX IF NOT EXISTS idx_prefs_onboarding
    ON user_preferences (onboarding_complete)
    WHERE onboarding_complete = true;

COMMIT;

-- Verify schema
SELECT
    column_name,
    data_type,
    udt_name,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'user_preferences'
ORDER BY ordinal_position;
