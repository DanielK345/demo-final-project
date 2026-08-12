import pytest

from src.agents.schemas import WorkflowType
from src.agents.state_store import (
    InMemoryStateStore,
    StateAlreadyExistsError,
    StateNotFoundError,
    StateVersionConflictError,
)


@pytest.mark.asyncio
async def test_store_creates_and_gets_isolated_state_copies():
    store = InMemoryStateStore()
    created = await store.create("session-001")

    created.collected_data["pickup"] = "Hồ Gươm"
    stored = await store.get("session-001")

    assert stored is not None
    assert stored.collected_data == {}
    assert stored.state_version == 0


@pytest.mark.asyncio
async def test_store_rejects_duplicate_session():
    store = InMemoryStateStore()
    await store.create("session-001")

    with pytest.raises(StateAlreadyExistsError):
        await store.create("session-001")


@pytest.mark.asyncio
async def test_store_updates_state_with_expected_version():
    store = InMemoryStateStore()
    await store.create("session-001")

    updated = await store.update(
        "session-001",
        {
            "current_workflow": WorkflowType.RIDE_BOOKING,
            "current_step": "COLLECT_PICKUP",
        },
        expected_version=0,
    )

    assert updated.current_workflow is WorkflowType.RIDE_BOOKING
    assert updated.state_version == 1


@pytest.mark.asyncio
async def test_store_rejects_stale_update():
    store = InMemoryStateStore()
    await store.create("session-001")
    await store.update("session-001", {"retry_count": 1}, expected_version=0)

    with pytest.raises(StateVersionConflictError):
        await store.update("session-001", {"retry_count": 2}, expected_version=0)


@pytest.mark.asyncio
async def test_store_keeps_sessions_isolated():
    store = InMemoryStateStore()
    await store.create("session-001")
    await store.create("session-002")

    await store.update(
        "session-001",
        {"collected_data": {"pickup": "Hồ Gươm"}},
        expected_version=0,
    )

    first = await store.get("session-001")
    second = await store.get("session-002")
    assert first is not None and first.collected_data["pickup"] == "Hồ Gươm"
    assert second is not None and second.collected_data == {}


@pytest.mark.asyncio
async def test_store_deletes_state():
    store = InMemoryStateStore()
    await store.create("session-001")

    await store.delete("session-001")

    assert await store.get("session-001") is None
    with pytest.raises(StateNotFoundError):
        await store.delete("session-001")
