from typing import Any, Protocol

from src.agents.state import AgentState


class StateNotFoundError(KeyError):
    pass


class StateAlreadyExistsError(ValueError):
    pass


class StateVersionConflictError(ValueError):
    pass


class StateStore(Protocol):
    async def create(self, session_id: str) -> AgentState: ...

    async def get(self, session_id: str) -> AgentState | None: ...

    async def update(
        self,
        session_id: str,
        updates: dict[str, Any],
        *,
        expected_version: int,
    ) -> AgentState: ...

    async def delete(self, session_id: str) -> None: ...


class InMemoryStateStore:
    """Non-production state store for deterministic tests and local development."""

    def __init__(self) -> None:
        self._states: dict[str, AgentState] = {}

    async def create(self, session_id: str) -> AgentState:
        if session_id in self._states:
            raise StateAlreadyExistsError(f"state already exists: {session_id}")

        state = AgentState(session_id=session_id)
        self._states[session_id] = state.model_copy(deep=True)
        return state.model_copy(deep=True)

    async def get(self, session_id: str) -> AgentState | None:
        state = self._states.get(session_id)
        return state.model_copy(deep=True) if state is not None else None

    async def update(
        self,
        session_id: str,
        updates: dict[str, Any],
        *,
        expected_version: int,
    ) -> AgentState:
        current = self._states.get(session_id)
        if current is None:
            raise StateNotFoundError(session_id)
        if current.state_version != expected_version:
            raise StateVersionConflictError(
                f"expected state version {expected_version}, "
                f"found {current.state_version}"
            )

        updated = current.apply(updates)
        self._states[session_id] = updated.model_copy(deep=True)
        return updated.model_copy(deep=True)

    async def delete(self, session_id: str) -> None:
        if session_id not in self._states:
            raise StateNotFoundError(session_id)
        del self._states[session_id]
