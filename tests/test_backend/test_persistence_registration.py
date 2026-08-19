from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.backend.db.models import PolicyAcceptance, User
from src.backend.repositories.persistence_repository import PersistenceRepository


class _AsyncContext:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args) -> None:
        return None


class _RecordingSession(_AsyncContext):
    def __init__(self) -> None:
        self.added: list[object] = []
        self.flush_snapshots: list[tuple[type, ...]] = []
        self.executed: list[object] = []

    def begin(self) -> _AsyncContext:
        return _AsyncContext()

    def add(self, row: object) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        self.flush_snapshots.append(tuple(type(row) for row in self.added))
        for row in self.added:
            if isinstance(row, User):
                row.two_factor_enabled = False
            if isinstance(row, PolicyAcceptance) and row.accepted_at is None:
                row.accepted_at = datetime.now(UTC)

    async def refresh(self, _row: object) -> None:
        return None

    async def execute(self, statement: object):
        self.executed.append(statement)
        return type("Result", (), {"rowcount": 1})()


@pytest.mark.asyncio
async def test_create_user_flushes_fk_parent_before_policy_acceptance() -> None:
    session = _RecordingSession()
    repository = PersistenceRepository(factory=lambda: session)  # type: ignore[arg-type]

    result = await repository.create_user(
        full_name="Người dùng mới",
        phone="0987654321",
        password_hash="test-hash",
        terms_version="2026-08-16",
        privacy_version="2026-08-16",
        source_sha256="a" * 64,
    )

    assert session.flush_snapshots == [(User,), (User, PolicyAcceptance)]
    assert result["phone"] == "0987654321"
    assert result["policy_acceptance"]["terms_version"] == "2026-08-16"


@pytest.mark.asyncio
async def test_revoke_token_updates_matching_durable_token() -> None:
    session = _RecordingSession()
    repository = PersistenceRepository(factory=lambda: session)  # type: ignore[arg-type]

    assert await repository.revoke_token("raw-token") is True
    assert len(session.executed) == 1
    assert "UPDATE auth_tokens" in str(session.executed[0])
