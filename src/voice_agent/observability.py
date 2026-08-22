"""Privacy-gated JSONL observability for one native LiveKit AgentSession."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from livekit.agents import AgentSession, llm
from pydantic import BaseModel

from src.voice_agent.session_data import AloSMSessionData

logger = logging.getLogger(__name__)

_EVENT_NAMES = (
    "user_state_changed",
    "agent_state_changed",
    "user_input_transcribed",
    "user_transcription_timeout",
    "conversation_item_added",
    "agent_false_interruption",
    "overlapping_speech",
    "function_tools_executed",
    "session_usage_updated",
    "speech_created",
    "tool_execution_updated",
    "error",
    "close",
)
_SAFE_METRIC_FIELDS = (
    "started_speaking_at",
    "stopped_speaking_at",
    "transcription_delay",
    "end_of_turn_delay",
    "on_user_turn_completed_delay",
    "llm_node_ttft",
    "tts_node_ttfb",
    "playback_latency",
    "e2e_latency",
)


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("._")
    return (cleaned or "unknown-call")[:96]


def _iso_timestamp(epoch_seconds: float | None = None) -> str:
    timestamp = epoch_seconds if epoch_seconds is not None else time.time()
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat(timespec="milliseconds")


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return _json_safe(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return str(value)


def _safe_metrics(metrics: dict[str, Any]) -> dict[str, object]:
    return {field: _json_safe(metrics[field]) for field in _SAFE_METRIC_FIELDS if metrics.get(field) is not None}


class SessionEventLog:
    """Append crash-tolerant JSON lines without changing the media pipeline."""

    def __init__(
        self,
        *,
        enabled: bool,
        include_transcripts: bool,
        directory: Path,
        userdata: AloSMSessionData,
        room_name: str,
    ) -> None:
        self.enabled = enabled
        self.include_transcripts = include_transcripts
        self.directory = directory
        self.userdata = userdata
        self.room_name = room_name
        self.path = directory / f"{_safe_filename(userdata.call_id)}.jsonl"
        self._started_monotonic = time.monotonic()
        self._queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=1000)
        self._writer_task: asyncio.Task[None] | None = None
        self._accepting = False

    async def start(self) -> None:
        if not self.enabled or self._writer_task is not None:
            return
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._accepting = True
            self._writer_task = asyncio.create_task(
                self._write_loop(),
                name=f"livekit-jsonl-{_safe_filename(self.userdata.call_id)}",
            )
            self.emit(
                "event_log_started",
                include_transcripts=self.include_transcripts,
                log_path=str(self.path),
            )
        except Exception:
            self._accepting = False
            self.enabled = False
            logger.exception("failed to start LiveKit JSONL event log")

    def emit(
        self,
        event_name: str,
        *,
        event_created_at: float | None = None,
        **fields: object,
    ) -> None:
        if not self.enabled or not self._accepting:
            return
        payload = {
            "schema_version": "1",
            "timestamp": _iso_timestamp(event_created_at),
            "elapsed_ms": round((time.monotonic() - self._started_monotonic) * 1000, 3),
            "event": event_name,
            "app_session_id": self.userdata.app_session_id,
            "call_id": self.userdata.call_id,
            "room_name": self.room_name,
            **{key: _json_safe(value) for key, value in fields.items()},
        }
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        try:
            self._queue.put_nowait(line)
        except asyncio.QueueFull:
            logger.warning("LiveKit JSONL event queue full", extra={"call_id": self.userdata.call_id})
            return

        terminal_fields = []
        for key in ("old_state", "new_state", "is_final", "role", "status", "resumed"):
            if key in payload:
                terminal_fields.append(f"{key}={payload[key]}")
        if self.include_transcripts and isinstance(payload.get("transcript"), str):
            terminal_fields.append(f"transcript={payload['transcript']!r}")
        suffix = " " + " ".join(terminal_fields) if terminal_fields else ""
        logger.info("[voice:%s] %s%s", self.userdata.call_id, event_name, suffix)

    async def close(self, reason: str = "") -> None:
        if not self.enabled or self._writer_task is None or not self._accepting:
            return
        self.emit("event_log_stopping", reason=reason or None)
        self._accepting = False
        await self._queue.put(None)
        try:
            await self._writer_task
        finally:
            self._writer_task = None

    async def _write_loop(self) -> None:
        try:
            with self.path.open("a", encoding="utf-8", buffering=1) as stream:
                while True:
                    line = await self._queue.get()
                    if line is None:
                        return
                    stream.write(line + "\n")
                    stream.flush()
        except Exception:
            logger.exception("LiveKit JSONL event writer failed", extra={"path": str(self.path)})


class LiveKitSessionObserver:
    """Translate public LiveKit session events into a stable, redacted schema."""

    def __init__(self, event_log: SessionEventLog) -> None:
        self.event_log = event_log
        self._tool_started_at: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}

    def register(self, session: AgentSession[AloSMSessionData]) -> None:
        for event_name in _EVENT_NAMES:
            session.on(event_name, self.record)

    def record(self, event: Any) -> None:
        event_name = str(getattr(event, "type", type(event).__name__))
        created_at = getattr(event, "created_at", None)
        fields = self._event_fields(event_name, event)
        self.event_log.emit(event_name, event_created_at=created_at, **fields)

    def _event_fields(self, event_name: str, event: Any) -> dict[str, object]:
        if event_name in {"agent_state_changed", "user_state_changed"}:
            return {"old_state": event.old_state, "new_state": event.new_state}

        if event_name == "user_input_transcribed":
            fields: dict[str, object] = {
                "is_final": event.is_final,
                "item_id": event.item_id,
                "language": event.language,
                "transcript_length": len(event.transcript),
            }
            if self.event_log.include_transcripts:
                fields["transcript"] = event.transcript
            return fields

        if event_name == "user_transcription_timeout":
            return {
                "speech_duration": event.speech_duration,
                "vad_speech_started_at": event.vad_speech_started_at,
            }

        if event_name == "conversation_item_added":
            item = event.item
            if not isinstance(item, llm.ChatMessage):
                return {"item_type": getattr(item, "type", type(item).__name__)}
            text = item.text_content or ""
            fields = {
                "item_type": item.type,
                "item_id": item.id,
                "role": item.role,
                "interrupted": item.interrupted,
                "transcript_confidence": item.transcript_confidence,
                "text_length": len(text),
                "metrics": _safe_metrics(item.metrics),
            }
            if self.event_log.include_transcripts:
                fields["text"] = text
            return fields

        if event_name == "speech_created":
            handle = event.speech_handle
            return {
                "speech_id": handle.id,
                "source": event.source,
                "user_initiated": event.user_initiated,
                "allow_interruptions": handle.allow_interruptions,
            }

        if event_name == "agent_false_interruption":
            return {"resumed": event.resumed}

        if event_name == "overlapping_speech":
            return {
                "is_interruption": event.is_interruption,
                "overlap_started_at": event.overlap_started_at,
                "detection_delay": event.detection_delay,
                "prediction_duration": event.prediction_duration,
                "probability": event.probability,
                "num_requests": event.num_requests,
            }

        if event_name == "tool_execution_updated":
            return self._tool_update_fields(event.update)

        if event_name == "function_tools_executed":
            tools = []
            for call, output in event.zipped():
                tools.append(
                    {
                        "call_id": call.call_id,
                        "name": call.name,
                        "status": "missing_output" if output is None else ("error" if output.is_error else "done"),
                    }
                )
            return {"tools": tools}

        if event_name == "session_usage_updated":
            return {"model_usage": _json_safe(event.usage.model_usage)}

        if event_name == "error":
            source = event.source
            return {
                "source_type": type(source).__name__,
                "provider": getattr(source, "provider", None),
                "model": getattr(source, "model", None),
                "error_type": type(event.error).__name__,
            }

        if event_name == "close":
            return {
                "reason": event.reason,
                "error_type": type(event.error).__name__ if event.error is not None else None,
            }

        return {}

    def _tool_update_fields(self, update: Any) -> dict[str, object]:
        update_type = str(update.type)
        if update_type == "tool_call_started":
            call = update.function_call
            self._tool_started_at[call.call_id] = time.monotonic()
            self._tool_names[call.call_id] = call.name
            return {"status": "started", "call_id": call.call_id, "tool_name": call.name}

        call_id = str(getattr(update, "call_id", ""))
        fields: dict[str, object] = {
            "status": getattr(update, "status", update_type),
            "call_id": call_id or None,
            "tool_name": self._tool_names.get(call_id),
        }
        if update_type == "tool_call_ended" and call_id in self._tool_started_at:
            fields["duration_ms"] = round(
                (time.monotonic() - self._tool_started_at.pop(call_id)) * 1000,
                3,
            )
            self._tool_names.pop(call_id, None)
        if update_type == "tool_reply_updated":
            fields = {
                "status": update.status,
                "speech_id": update.speech_id,
                "update_count": len(update.update_ids),
            }
        return fields
