-- Run in Supabase: SQL Editor → New query → Run.
-- Use this if the API could not run CREATE TABLE (e.g. IPv4-only laptop + IPv6-only direct URL,
-- or Transaction pooler / port 6543 where DDL is not appropriate).

CREATE TABLE IF NOT EXISTS public.users (
    id SERIAL PRIMARY KEY,
    google_id VARCHAR NOT NULL UNIQUE,
    email VARCHAR,
    name VARCHAR,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

COMMENT ON TABLE public.users IS 'App users (mirrors SQLAlchemy model in src/db/postgres.py)';
