from typing import TYPE_CHECKING, Any

from src.agents.core.booking.state import BookingData, BookingStep

if TYPE_CHECKING:
    from src.agents.legacy.workflows.booking.workflow import RideBookingWorkflow

__all__ = ["BookingData", "BookingStep", "RideBookingWorkflow"]


def __getattr__(name: str) -> Any:
    if name == "RideBookingWorkflow":
        from src.agents.legacy.workflows.booking.workflow import RideBookingWorkflow

        return RideBookingWorkflow
    raise AttributeError(name)
