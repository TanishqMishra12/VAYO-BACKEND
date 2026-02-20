-- =============================================================================
-- Clerk Integration Migration
-- =============================================================================
-- Run ONCE against your existing database:
--   psql -d community_matching -f matching_system/clerk_migration.sql
--
-- What this does:
--   1. Makes the `username` column nullable (Clerk doesn't always provide one)
--   2. Adds Clerk-specific columns to the `users` table
--   3. Creates a performance index on the new `email` column
-- =============================================================================

BEGIN;

-- Step 1: Make username nullable
--   (Clerk provides first_name/last_name instead of a combined username)
ALTER TABLE users
    ALTER COLUMN username DROP NOT NULL;

-- Step 2: Add Clerk-synced columns
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email           TEXT,
    ADD COLUMN IF NOT EXISTS first_name      TEXT,
    ADD COLUMN IF NOT EXISTS last_name       TEXT,
    ADD COLUMN IF NOT EXISTS public_metadata JSONB    DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS is_active       BOOLEAN  DEFAULT true;

-- Step 3: Index on email for fast lookups
CREATE INDEX IF NOT EXISTS idx_users_email
    ON users (email)
    WHERE email IS NOT NULL;

-- Step 4: Mark all existing users as active (backward-compatible default)
UPDATE users SET is_active = true WHERE is_active IS NULL;

COMMIT;

-- Verify
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name = 'users'
ORDER BY ordinal_position;
