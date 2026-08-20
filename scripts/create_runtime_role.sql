-- ==============================================================================
-- AloSM Production Least-Privilege Runtime Role Setup (P0.3 Runbook)
-- Run this in Supabase SQL Editor as Postgres Admin / Migration Owner
-- ==============================================================================

-- 1. Create runtime role with secure password (REPLACE WITH YOUR OWN PASSWORD)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'alosm_app_runtime') THEN
        CREATE ROLE alosm_app_runtime WITH LOGIN PASSWORD 'CHANGE_ME_STRONG_RUNTIME_PASSWORD_123!';
    END IF;
END $$;

-- 2. Revoke superuser/admin privileges
ALTER ROLE alosm_app_runtime WITH NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT;

-- 3. Grant schema usage
GRANT CONNECT ON DATABASE postgres TO alosm_app_runtime;
GRANT USAGE ON SCHEMA public TO alosm_app_runtime;

-- 4. Grant explicit DML (SELECT, INSERT, UPDATE, DELETE) only on runtime tables
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO alosm_app_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO alosm_app_runtime;

-- 5. Configure default privileges for any future tables created by migrations
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO alosm_app_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO alosm_app_runtime;

-- 6. Verification query (all flags MUST be false)
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls
FROM pg_roles 
WHERE rolname = 'alosm_app_runtime';
