"""Backend service exports without eager application startup side effects."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.backend.services.booking_service import BookingService
    from src.backend.services.call_service import CallService
    from src.backend.services.handoff_service import HandoffService
    from src.backend.services.session_service import SessionService
    from src.backend.services.trip_service import TripService

__all__ = ["BookingService", "CallService", "HandoffService", "SessionService", "TripService"]

_EXPORTS = {
    "BookingService": "src.backend.services.booking_service",
    "CallService": "src.backend.services.call_service",
    "HandoffService": "src.backend.services.handoff_service",
    "SessionService": "src.backend.services.session_service",
    "TripService": "src.backend.services.trip_service",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    return getattr(import_module(module_name), name)
