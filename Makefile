.PHONY: run livekit-backend livekit-worker livekit-frontend seed-demo-operator test lint format typecheck check clean

run:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

livekit-backend:
	uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

livekit-worker:
	uv run python -m src.voice_agent.server dev

livekit-frontend:
	cd src/frontend && npm run dev

seed-demo-operator:
	uv run python -m scripts.seed_demo_operator

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
