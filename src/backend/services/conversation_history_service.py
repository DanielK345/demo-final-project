from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.backend.config import get_settings
from src.backend.repositories.persistence_repository import PersistenceRepository

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_LOGS_DIR = _PROJECT_ROOT / "logs"


class ConversationHistoryService:
    """Đọc lại log hội thoại do `ConversationLogger` ghi (`logs/*.json`) — phục vụ
    tính năng "Lịch sử trò chuyện" (list session + xem lại transcript) trên Frontend.

    Đọc trực tiếp từ file thay vì `SessionService.sessions` (in-memory) vì mục đích
    của tính năng này là xem lại session CŨ, đã kết thúc từ lâu — có thể không còn
    trong dict in-memory (mất khi server restart), nhưng file log vẫn còn.
    """

    def __init__(self, logs_dir: Path | None = None, repository: PersistenceRepository | None = None) -> None:
        self.logs_dir = logs_dir or _LOGS_DIR
        self._repository = repository or PersistenceRepository()

    async def list_sessions_durable(self, user_id: str) -> list[dict[str, Any]]:
        if get_settings().app_env == "test":
            return self.list_sessions(user_id)
        summaries: list[dict[str, Any]] = []
        for session in await self._repository.list_sessions(user_id):
            messages = await self._repository.conversation_messages(str(session["session_id"]))
            if not messages:
                continue
            first = next((str(item["text"]) for item in messages if item["role"] == "user"), "")
            summaries.append(
                {
                    "session_id": session["session_id"],
                    "channel": session["channel"],
                    "status": session["status"],
                    "created_at": session["created_at"],
                    "message_count": len(messages),
                    "preview": first[:120],
                }
            )
        return summaries

    async def get_transcript_durable(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        if get_settings().app_env == "test":
            return self.get_transcript(user_id, session_id)
        session = await self._repository.get_session(session_id)
        if session is None or session.get("user_id") != user_id:
            return None
        return {
            "session_id": session_id,
            "channel": session["channel"],
            "status": session["status"],
            "created_at": session["created_at"],
            "ended_at": session["ended_at"],
            "messages": await self._repository.conversation_messages(session_id),
        }

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for path in self._iter_logs():
            payload = self._safe_read(path)
            if payload is None or payload.get("user_id") != user_id:
                continue
            messages = payload.get("messages") or []
            if not messages:
                continue  # bỏ qua session rỗng (tạo xong nhưng chưa nói gì)
            first_user_message = next(
                (m.get("text", "") for m in messages if m.get("role") == "user"),
                "",
            )
            summaries.append(
                {
                    "session_id": payload["session_id"],
                    "channel": payload.get("channel", "WEB_TEXT"),
                    "status": payload.get("status", "ACTIVE"),
                    "created_at": payload.get("created_at"),
                    "message_count": len(messages),
                    "preview": first_user_message[:120],
                }
            )
        summaries.sort(key=lambda item: item["created_at"] or "", reverse=True)
        return summaries

    def get_transcript(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        for path in self._iter_logs():
            payload = self._safe_read(path)
            if payload is None or payload.get("session_id") != session_id:
                continue
            if payload.get("user_id") != user_id:
                return None  # tồn tại nhưng không phải chủ session -> coi như không thấy
            return payload
        return None

    def _iter_logs(self) -> list[Path]:
        if not self.logs_dir.is_dir():
            return []
        return sorted(self.logs_dir.glob("*.json"), reverse=True)

    @staticmethod
    def _safe_read(path: Path) -> dict[str, Any] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
