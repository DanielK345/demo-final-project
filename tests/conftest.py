import os
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Unit tests must remain deterministic even when local development enables the
# real provider in .env. Provider tests instantiate their adapter explicitly.
os.environ["AGENT_LLM_ENABLED"] = "false"
os.environ["AGENT_REWRITE_ENABLED"] = "false"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./data/test.db"

from src.backend.services.conversation_logger import ConversationLogger
from src.backend.services.session_service import SessionService
from src.main import app


@pytest.fixture(autouse=True)
def _isolate_conversation_logs(tmp_path, monkeypatch):
    """Mọi session tạo trong test (kể cả gián tiếp — vd login tạo session, test
    voice/session bridge...) đều ghi log hội thoại thật ra `logs/` mặc định, vì
    `SessionService._conversation_logger` là class attribute dùng chung. Trước khi có
    fixture này, chạy `pytest` một lần tạo ~150-200 file rác trong `logs/` — không chỉ
    tốn đĩa mà giờ còn lẫn vào tính năng "Lịch sử trò chuyện" (đọc trực tiếp từ
    `logs/*.json`) nếu ai chạy pytest trên máy đang chạy server thật. Đổi sang thư mục
    tạm riêng cho từng test, tự dọn sau khi test xong (tmp_path).

    `tests/test_backend/test_conversation_logger.py` tự inject `ConversationLogger`
    riêng (constructor hoặc monkeypatch cục bộ trong test) nên không bị ảnh hưởng —
    patch ở đây chỉ là giá trị mặc định, vẫn ghi đè được bình thường."""
    monkeypatch.setattr(SessionService, "_conversation_logger", ConversationLogger(logs_dir=tmp_path / "logs"))


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing API endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_llm():
    """Mock LLM to avoid calling OpenAI during tests.

    Usage in test:
        def test_something(mock_llm):
            # LLM calls will return mock response instead of hitting OpenAI
            ...
    """
    mock = AsyncMock()
    mock.ainvoke.return_value = AsyncMock(content="Mocked LLM response")
    return mock
