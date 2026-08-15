from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOGS_DIR = _PROJECT_ROOT / "logs"
_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class ConversationLogger:
    """Append user/agent turns to a session JSON log under logs/."""

    def __init__(self, logs_dir: Path | None = None) -> None:
        self.logs_dir = logs_dir or _LOGS_DIR
        self._lock = threading.Lock()

    def start_session(
        self,
        *,
        session_id: str,
        user_id: str,
        channel: str,
        device_id: str | None = None,
        created_at: datetime | None = None,
    ) -> Path:
        started = created_at or datetime.now(_VN_TZ)
        path = self._new_log_path(session_id, started)
        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "channel": channel,
            "device_id": device_id,
            "created_at": started.isoformat(),
            "updated_at": started.isoformat(),
            "status": "ACTIVE",
            "log_file": path.name,
            "messages": [],
        }
        self._write(path, payload)
        return path

    def log_turn(
        self,
        log_file: str | Path,
        *,
        user_message: str,
        source: str = "TEXT",
        stt_confidence: float | None = None,
        agent_message: str,
        message_id: str,
        action: str,
        state: dict[str, Any] | None = None,
        booking: dict[str, Any] | None = None,
    ) -> None:
        path = Path(log_file)
        if not path.is_absolute():
            path = self.logs_dir / path

        now = datetime.now(_VN_TZ).isoformat()
        user_entry: dict[str, Any] = {
            "timestamp": now,
            "role": "user",
            "text": user_message,
            "source": source,
        }
        if stt_confidence is not None:
            user_entry["stt_confidence"] = stt_confidence

        agent_entry: dict[str, Any] = {
            "timestamp": now,
            "role": "agent",
            "text": agent_message,
            "message_id": message_id,
            "action": action,
        }
        if state is not None:
            agent_entry["state"] = state
        if booking is not None:
            agent_entry["booking"] = booking

        with self._lock:
            payload = self._read(path)
            payload["messages"].extend([user_entry, agent_entry])
            payload["updated_at"] = now
            self._write(path, payload)

    def end_session(self, log_file: str | Path, *, reason: str) -> None:
        path = Path(log_file)
        if not path.is_absolute():
            path = self.logs_dir / path

        now = datetime.now(_VN_TZ).isoformat()
        with self._lock:
            if not path.exists():
                return
            payload = self._read(path)
            payload["status"] = "ENDED"
            payload["end_reason"] = reason
            payload["ended_at"] = now
            payload["updated_at"] = now
            self._write(path, payload)

    def _new_log_path(self, session_id: str, started: datetime) -> Path:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        base = started.strftime("%Y-%m-%d-%H-%M-%S")
        suffix = session_id.removeprefix("sess_")[:8]
        path = self.logs_dir / f"{base}_{suffix}.json"
        counter = 1
        while path.exists():
            path = self.logs_dir / f"{base}_{suffix}_{counter}.json"
            counter += 1
        return path

    @staticmethod
    def _read(path: Path) -> dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(path)
