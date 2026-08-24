from copy import deepcopy
from threading import RLock

from src.backend.repositories.base import BaseRepository


class HandoffRepository(BaseRepository):
    """Process-local repository with lifecycle semantics and safe copies."""

    def __init__(self) -> None:
        super().__init__()
        self._lock = RLock()

    def create(self, record: dict[str, object]) -> dict[str, object]:
        handoff_id = str(record["handoff_id"])
        with self._lock:
            self._store[handoff_id] = deepcopy(record)
            return deepcopy(record)

    def get(self, handoff_id: str) -> dict[str, object] | None:
        with self._lock:
            value = self._store.get(handoff_id)
            return deepcopy(value) if isinstance(value, dict) else None

    def list_by_status(self, status: str) -> list[dict[str, object]]:
        with self._lock:
            records = [
                deepcopy(value)
                for value in self._store.values()
                if isinstance(value, dict) and value.get("status") == status
            ]
        return sorted(
            records,
            key=lambda item: (-int(item.get("priority", 0)), str(item.get("created_at", ""))),
        )

    def update(self, handoff_id: str, updates: dict[str, object]) -> dict[str, object] | None:
        with self._lock:
            current = self._store.get(handoff_id)
            if not isinstance(current, dict):
                return None
            current.update(deepcopy(updates))
            return deepcopy(current)


_repository = HandoffRepository()


def get_handoff_repository() -> HandoffRepository:
    return _repository
