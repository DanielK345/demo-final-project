# Backend

This folder contains the FastAPI backend for the AloSM Voice AI project. It is the application layer that exposes the API, coordinates the LangGraph agent, and connects to session, booking, trip, handoff, and observability components.

## What this backend does

- Serves the HTTP API used by the voice and operator flows.
- Exposes the LangGraph-powered chat route used by the current test suite.
- Manages sessions, bookings, trips, and handoffs through controller and service layers.
- Provides health and readiness endpoints for runtime checks.
- Wraps external systems such as Redis, PostgreSQL, ASR, TTS, maps, and booking integrations.

## Entry point

The FastAPI application is created in [main.py](main.py) and includes:

- API routes under `/api/v1`
- `GET /health`
- `GET /ready`

## API surface

### Calls

- `POST /api/v1/calls`
- `WS /api/v1/calls/{call_id}/stream`

### Sessions

- `GET /api/v1/sessions/{session_id}`
- `PATCH /api/v1/sessions/{session_id}`
- `POST /api/v1/sessions/{session_id}/resume`

### Bookings

- `POST /api/v1/bookings`

### Trips

- `GET /api/v1/trips/status?session_id=...`

### Handoffs

- `POST /api/v1/handoffs`
- `GET /api/v1/handoffs?status=pending`
- `POST /api/v1/handoffs/{handoff_id}/accept`

### Legacy compatibility routes

- `POST /api/v1/chat`
- `GET /api/v1/status`

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
- The current `/chat` route is kept for compatibility and delegates to the LangGraph agent.
