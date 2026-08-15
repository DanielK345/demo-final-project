# Backend

This folder contains the FastAPI backend for the AloSM Voice booking MVP. It is the application layer for the two customer-facing web pages: authentication and a voice/text booking homepage.

## What this backend does

- Serves authenticated browser sessions and text/voice conversation turns.
- Collects pickup and destination in a server-side session.
- Requires an explicit confirmation before creating a booking.
- Uses an idempotency key for every booking creation.
- Provides health and readiness endpoints for runtime checks.
- Wraps external systems such as Redis, PostgreSQL, ASR, TTS, maps, and booking integrations.

## Entry point

The FastAPI application is created in [main.py](main.py) and includes:

- API routes under `/api/v1`
- `GET /health`
- `GET /ready`

## API surface

### Authentication

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

### Voice/text booking session

- `POST /api/v1/sessions` — starts a browser session (Bearer token required)
- `POST /api/v1/sessions/{session_id}/messages` — sends a text or voice transcript
- `POST /api/v1/sessions/{session_id}/end`
- `GET`, `PATCH`, `POST /api/v1/sessions/{session_id}/resume`

### Booking

- `POST /api/v1/bookings` — requires `Idempotency-Key` and `fare_confirmed: true`

The service deliberately does not expose customer live tracking, trip history, payment, or wallet features in this MVP.

## Project layout

- `api/` route definitions and dependency wiring
- `controllers/` request orchestration and validation
- `services/` business logic
- `agents/` LangGraph state, nodes, policies, and tools
- `integrations/` external client adapters
- `repositories/` data access layer
- `schemas/` request and response DTOs
- `models/` domain models
- `workers/` background worker configuration and tasks
- `observability/` logging, metrics, and tracing helpers

## Configuration

Runtime settings are defined in [config.py](config.py) and loaded from environment variables or a local `.env` file.

Important settings:

- `app_name`
- `app_env`
- `app_port`
- `app_host`
- `log_level`
- `cors_origins`
- `openai_api_key`
- `model_name`
- `llm_temperature`
- `database_url`
- `chroma_persist_dir`

## Local run

From the repository root, install dependencies and run the app with Uvicorn.

```bash
uvicorn src.backend.main:app --reload
```

If you need a different host or port, pass them explicitly:

```bash
uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Runtime dependencies

This backend expects the project dependencies to include:

- FastAPI and Uvicorn
- Pydantic and Pydantic Settings
- LangChain, LangChain OpenAI, and LangGraph
- Redis for session and worker support
- PostgreSQL access via SQLAlchemy, Alembic, and psycopg2-binary
- Celery for background jobs

## Notes

- `GET /health` returns the current environment.
- `GET /ready` is a lightweight readiness check.
- The current in-memory adapters make the demo self-contained. Replace them with password hashing, PostgreSQL/Redis and real booking/voice providers before production.
