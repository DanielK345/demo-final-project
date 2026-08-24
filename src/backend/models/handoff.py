from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class HandoffRecord:
    id: str
    call_id: str
    reason: str
    summary: str
    pending_action: str | None
    status: str
    created_at: datetime
