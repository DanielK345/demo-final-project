"""Durable business-state boundary for the LiveKit AgentSession."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from src.backend.repositories.persistence_repository import PersistenceRepository
from src.voice_agent.session_data import AloSMSessionData


class VoiceStateConflictError(RuntimeError):
    """Another room already advanced the same application session."""


class VoiceStateStore(Protocol):
    async def restore(self, userdata: AloSMSessionData) -> bool: ...

    async def save(self, userdata: AloSMSessionData) -> None: ...


class VoiceStateRepository(Protocol):
    async def get_voice_agent_state(self, session_id: str) -> dict[str, object] | None: ...

    async def save_voice_agent_state(
        self,
        session_id: str,
        state: Mapping[str, object],
        *,
        expected_revision: int,
    ) -> dict[str, object] | None: ...


class DatabaseVoiceStateStore:
    def __init__(self, repository: VoiceStateRepository | None = None) -> None:
        self._repository = repository or PersistenceRepository()

    async def restore(self, userdata: AloSMSessionData) -> bool:
        row = await self._repository.get_voice_agent_state(userdata.app_session_id)
        if row is None:
            userdata.persistence_enabled = False
            return False

        # The trusted session row, not client/job metadata, owns the account ID.
        userdata.user_id = str(row["user_id"])
        userdata.persistence_revision = int(row["revision"])
        state = row.get("state")
        if not isinstance(state, dict):
            return False
        userdata.restore(state, userdata.persistence_revision)
        return True

    async def save(self, userdata: AloSMSessionData) -> None:
        if not userdata.persistence_enabled:
            return
        result = await self._repository.save_voice_agent_state(
            userdata.app_session_id,
            userdata.durable_state(),
            expected_revision=userdata.persistence_revision,
        )
        if result is None:
            raise VoiceStateConflictError("VOICE_STATE_CONFLICT")
        userdata.persistence_revision = int(result["revision"])


class EphemeralVoiceStateStore:
    """No-op store used only by isolated unit/synthetic worker smoke sessions."""

    async def restore(self, userdata: AloSMSessionData) -> bool:
        userdata.persistence_enabled = False
        return False

    async def save(self, userdata: AloSMSessionData) -> None:
        return None
