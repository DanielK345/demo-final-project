"""Durable business-state boundary for the LiveKit AgentSession."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
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

    async def update_session(
        self,
        session_id: str,
        updates: Mapping[str, object],
        *,
        expected_version: int | None = None,
    ) -> dict[str, object] | None: ...


class DatabaseVoiceStateStore:
    def __init__(self, repository: VoiceStateRepository | None = None) -> None:
        self._repository = repository or PersistenceRepository()

    async def restore(self, userdata: AloSMSessionData) -> bool:
        row = await self._repository.get_voice_agent_state(userdata.app_session_id)
        if row is None:
            userdata.persistence_enabled = False
            return False
        if row.get("status") not in {None, "ACTIVE"}:
            userdata.persistence_enabled = False
            return False
        state = row.get("state")
        if isinstance(state, dict):
            draft = state.get("booking_draft")
            draft = draft if isinstance(draft, dict) else {}
            if state.get("lifecycle_status") in {"completed", "cancelled"} or draft.get("booking"):
                userdata.persistence_enabled = False
                return False

        # The trusted session row, not client/job metadata, owns the account ID.
        userdata.user_id = str(row["user_id"])
        userdata.persistence_revision = int(row["revision"])
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
        if userdata.lifecycle_status in {"completed", "cancelled"}:
            reason = "BOOKING_COMPLETED" if userdata.lifecycle_status == "completed" else "USER_CANCELLED"
            await self._repository.update_session(
                userdata.app_session_id,
                {
                    "status": "ENDED",
                    "end_reason": reason,
                    "ended_at": datetime.now(UTC),
                },
            )


class EphemeralVoiceStateStore:
    """No-op store used only by isolated unit/synthetic worker smoke sessions."""

    async def restore(self, userdata: AloSMSessionData) -> bool:
        userdata.persistence_enabled = False
        return False

    async def save(self, userdata: AloSMSessionData) -> None:
        return None
