.PHONY: backend run livekit-backend livekit-worker livekit-frontend test lint format typecheck check clean

backend: run

run:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

livekit-backend:
	VOICE_RUNTIME=livekit uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

livekit-worker:
	VOICE_RUNTIME=livekit uv run python -m src.voice_agent.server dev

livekit-frontend:
	cd src/frontend && VITE_VOICE_RUNTIME=livekit npm run dev

test:
	pytest tests/ -v

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

check: lint format test

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
