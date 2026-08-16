"""Shared settings entrypoint for agent and backend code.

``src.backend.config`` owns the concrete settings model.  Keeping this module
as a re-export preserves the import path used by the standalone agent package
and prevents the two configuration models from drifting after branch merges.
"""

from src.backend.config import Settings, get_settings

__all__ = ["Settings", "get_settings"]
