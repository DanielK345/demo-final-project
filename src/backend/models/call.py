from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class CallRecord:
    id: str
    customer_phone_hash: str
    started_at: datetime
    ended_at: datetime | None
    status: str
