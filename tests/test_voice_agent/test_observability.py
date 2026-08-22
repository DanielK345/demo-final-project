import json
from pathlib import Path

import pytest
from livekit.agents import (
    ConversationItemAddedEvent,
    FunctionToolsExecutedEvent,
    UserInputTranscribedEvent,
    UserTranscriptionTimeoutEvent,
    llm,
)

from src.voice_agent.observability import LiveKitSessionObserver, SessionEventLog
from src.voice_agent.session_data import AloSMSessionData


def _userdata(call_id: str = "call/livekit:1") -> AloSMSessionData:
    return AloSMSessionData(
        app_session_id="session-livekit",
        call_id=call_id,
        user_id="user",
        participant_identity="participant",
    )


def _read_events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


@pytest.mark.asyncio
async def test_jsonl_observability_redacts_transcripts_by_default(tmp_path: Path) -> None:
    event_log = SessionEventLog(
        enabled=True,
        include_transcripts=False,
        directory=tmp_path,
        userdata=_userdata(),
        room_name="room-1",
    )
    observer = LiveKitSessionObserver(event_log)
    await event_log.start()

    observer.record(
        UserInputTranscribedEvent(
            transcript="đón tôi ở địa chỉ riêng tư",
            is_final=True,
            language="vi",
        )
    )
    observer.record(
        ConversationItemAddedEvent(
            item=llm.ChatMessage(
                role="user",
                content=["đón tôi ở địa chỉ riêng tư"],
                transcript_confidence=0.71,
                metrics={"transcription_delay": 0.2, "end_of_turn_delay": 0.8},
            )
        )
    )
    await event_log.close("test")

    raw = event_log.path.read_text(encoding="utf-8")
    events = _read_events(event_log.path)
    transcript_event = next(event for event in events if event["event"] == "user_input_transcribed")
    message_event = next(event for event in events if event["event"] == "conversation_item_added")

    assert "địa chỉ riêng tư" not in raw
    assert transcript_event["transcript_length"] == len("đón tôi ở địa chỉ riêng tư")
    assert "transcript" not in transcript_event
    assert message_event["transcript_confidence"] == 0.71
    assert message_event["metrics"] == {"transcription_delay": 0.2, "end_of_turn_delay": 0.8}
    assert event_log.path.name == "call_livekit_1.jsonl"


@pytest.mark.asyncio
async def test_jsonl_observability_can_explicitly_include_transcripts(tmp_path: Path) -> None:
    event_log = SessionEventLog(
        enabled=True,
        include_transcripts=True,
        directory=tmp_path,
        userdata=_userdata("call-2"),
        room_name="room-2",
    )
    observer = LiveKitSessionObserver(event_log)
    await event_log.start()
    observer.record(UserInputTranscribedEvent(transcript="đúng rồi", is_final=True))
    await event_log.close()

    event = next(item for item in _read_events(event_log.path) if item["event"] == "user_input_transcribed")
    assert event["transcript"] == "đúng rồi"


@pytest.mark.asyncio
async def test_jsonl_observability_records_native_transcription_timeout_without_audio(
    tmp_path: Path,
) -> None:
    event_log = SessionEventLog(
        enabled=True,
        include_transcripts=False,
        directory=tmp_path,
        userdata=_userdata("call-timeout"),
        room_name="room-timeout",
    )
    observer = LiveKitSessionObserver(event_log)
    await event_log.start()
    observer.record(
        UserTranscriptionTimeoutEvent(
            speech_duration=1.25,
            vad_speech_started_at=123.5,
        )
    )
    await event_log.close()

    event = next(
        item for item in _read_events(event_log.path) if item["event"] == "user_transcription_timeout"
    )
    assert event["speech_duration"] == 1.25
    assert event["vad_speech_started_at"] == 123.5
    assert "transcript" not in event


@pytest.mark.asyncio
async def test_tool_logs_never_include_arguments_or_outputs(tmp_path: Path) -> None:
    event_log = SessionEventLog(
        enabled=True,
        include_transcripts=True,
        directory=tmp_path,
        userdata=_userdata("call-3"),
        room_name="room-3",
    )
    observer = LiveKitSessionObserver(event_log)
    await event_log.start()
    call = llm.FunctionCall(
        call_id="tool-1",
        name="search_place",
        arguments='{"query":"địa chỉ bí mật"}',
    )
    output = llm.FunctionCallOutput(
        call_id="tool-1",
        name="search_place",
        output="provider payload bí mật",
        is_error=False,
    )
    observer.record(
        FunctionToolsExecutedEvent(
            function_calls=[call],
            function_call_outputs=[output],
        )
    )
    await event_log.close()

    raw = event_log.path.read_text(encoding="utf-8")
    assert "search_place" in raw
    assert "địa chỉ bí mật" not in raw
    assert "provider payload bí mật" not in raw


@pytest.mark.asyncio
async def test_disabled_observability_does_not_create_a_file(tmp_path: Path) -> None:
    event_log = SessionEventLog(
        enabled=False,
        include_transcripts=False,
        directory=tmp_path,
        userdata=_userdata("call-4"),
        room_name="room-4",
    )

    await event_log.start()
    event_log.emit("should_not_exist")
    await event_log.close()

    assert not event_log.path.exists()
