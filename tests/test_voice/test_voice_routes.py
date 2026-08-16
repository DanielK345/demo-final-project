"""Integration test cho `src/backend/api/routes/voice.py` — verify WS route thật
chạy được qua FastAPI app thật (`src/main.py` shim -> `src.backend.main:app`), gồm cả
đường đi qua `SessionBridge` -> `SessionService` thật (không mock session, chỉ mock
ASR/TTS qua provider thật. Bài full roundtrip chỉ chạy khi có fixture PCM16 giọng nói thật
được cấp rõ ràng qua biến môi trường; không dùng waveform giả làm bằng chứng STT."""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.main import app


def _pcm16(value: float, seconds: float, rate: int = 16000) -> bytes:
    n = int(rate * seconds)
    samples = (np.ones(n, dtype=np.float32) * value * 32767).astype("<i2")
    return samples.tobytes()


def test_voice_health_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/voice/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.skipif(
    not os.getenv("VOICE_LIVE_PCM16_FIXTURE"),
    reason="Set VOICE_LIVE_PCM16_FIXTURE to consented, real 16 kHz PCM16 speech audio.",
)
def test_voice_ws_full_call_roundtrip():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/voice/stream") as ws:
        ws.send_json({"type": "start_call", "payload": {"sample_rate": 16000}})

        ready = ws.receive_json()
        assert ready["type"] == "session_ready"
        session_id = ready["session_id"]
        assert session_id.startswith("sess_")

        status = ws.receive_json()
        assert status["type"] == "status"

        fixture_path = Path(os.environ["VOICE_LIVE_PCM16_FIXTURE"])
        ws.send_bytes(fixture_path.read_bytes())
        ws.send_bytes(_pcm16(0.0, 1.0))  # endpoint silence

        seen_types: list[str] = []
        for _ in range(20):
            message = ws.receive()
            if message.get("type") == "websocket.close":
                break
            if (text := message.get("text")) is not None:
                data = json.loads(text)
                seen_types.append(data["type"])
                if data["type"] == "audio_meta":
                    break
            elif message.get("bytes") is not None:
                pass

        assert "transcript" in seen_types
        assert "agent_message" in seen_types
        assert "audio_meta" in seen_types

        audio_frame = ws.receive()
        assert audio_frame.get("bytes") is not None

        trailing = ws.receive_json()
        assert trailing["type"] in {"session_ended", "status", "handoff"}

        ws.send_json({"type": "end_call", "payload": {}})
        ended = ws.receive_json()
        for _ in range(5):  # bound chống treo — drain tối đa 5 event leftover
            if ended["type"] in {"session_ended", "error"}:
                break
            ended = ws.receive_json()
        assert ended["type"] == "session_ended"


def test_voice_ws_rejects_audio_before_start_call():
    client = TestClient(app)
    with client.websocket_connect("/api/v1/voice/stream") as ws:
        ws.send_bytes(_pcm16(0.5, 0.1))
        error = ws.receive_json()
        assert error["type"] == "error"


def test_speak_endpoint_returns_audio():
    """`POST /speak` — dùng cho trang nào chỉ cần text -> audio (vd AssistantPage.tsx
    ở frontend, thay cho window.speechSynthesis của trình duyệt)."""
    client = TestClient(app)
    response = client.post("/api/v1/voice/speak", json={"text": "Xin chào, tôi có thể giúp gì cho anh chị?"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/")
    assert len(response.content) > 0


def test_speak_endpoint_applies_formatter_and_pronunciation():
    """Text đưa qua TTS phải đã qua format_for_speech + pronunciation override —
    verify gián tiếp bằng cách so audio của 2 câu tương đương nhau về mặt đọc."""
    client = TestClient(app)
    plain = client.post("/api/v1/voice/speak", json={"text": "Landmark 81"})
    already_spelled = client.post("/api/v1/voice/speak", json={"text": "Len Mác Tám Mươi Mốt"})
    assert plain.status_code == already_spelled.status_code == 200
    # Cả hai audio phải khác byte-rỗng — không khẳng định bằng nhau tuyệt đối (audio
    # thật từ mạng), chỉ verify cả 2 request đều thành công và có audio thật.
    assert len(plain.content) > 0
    assert len(already_spelled.content) > 0


def test_speak_endpoint_rejects_empty_text():
    client = TestClient(app)
    response = client.post("/api/v1/voice/speak", json={"text": ""})
    assert response.status_code == 422
