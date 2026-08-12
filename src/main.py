"""Stable ASGI entrypoint for tooling and tests.

The application lives in ``src.backend``; this module preserves the standard
``src.main:app`` import path used by the test suite and deployment commands.
"""

from src.backend.main import app

__all__ = ["app"]
