# Database verification

Date: **2026-08-16** · Branch: `feature/voice-ai` · Baseline commit: `738ea18`.

| Field | Actual |
|---|---|
| Environment | Local `.venv`, remote Supabase/Postgres credentials from untracked `.env` |
| Secret handling | `.env` ignored and not tracked; values were not printed |
| Drivers | SQLAlchemy 2.0.52, asyncpg 0.31.0, psycopg2-binary 2.9.12, Alembic 1.19.1 |
| `alembic heads` | `0002_handoff_operations (head)` |
| `alembic current` | `0002_handoff_operations (head)` against PostgreSQL |
| History | `0001_initial -> 0002_handoff_operations` |
| Runtime readiness | Timed `SELECT 1`; safe 503 without connection details |

Status: database connectivity and migration alignment are `LIVE_VALIDATED`. Application persistence
is only `STAGING_ONLY`: primary services still use process-memory despite ORM tables. Restart and
multi-instance persistence therefore remain **not passed** and are internal engineering work.

Supabase changelog review: 2026 Data API no longer auto-exposes new tables. This application currently
uses direct SQLAlchemy connections; if Data API access is later enabled, explicit grants and ownership
RLS policies must be reviewed together. No permissive RLS policy was invented in this change.
