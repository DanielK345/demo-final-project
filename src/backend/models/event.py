from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ConversationEvent:
    id: int | None
    call_id: str
    event_type: str
    intent: str | None
    action: str | None
    metadata: dict[str, object]
    created_at: datetime
