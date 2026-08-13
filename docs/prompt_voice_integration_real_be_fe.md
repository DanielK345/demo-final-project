# Prompt — Tích hợp Voice AI vào project thật (có BE/FE/agentic đã build)

**Dùng để làm gì:** Prompt tự chứa để tích hợp toàn bộ code Voice AI (đã hoàn thiện Phần
1-8 trên nhánh `feature/voice-ai`, sao lưu tại `C:\Users\KHANH\Documents\GitHub\P-160 copy`)
vào project thật hiện đang checkout `feature/backend-data` tại
`C:\Users\KHANH\Documents\GitHub\P-160` — nơi đã có Backend/Frontend/Agentic của người
khác. Nguyên tắc bắt buộc: **chỉ bổ sung (additive), không được đổi hành vi bất kỳ file
nào người khác đã viết.**

---

## PROMPT

### Bối cảnh đã xác nhận bằng cách đọc code thật (không đoán)

1. App thật chạy từ `src/backend/main.py` (`src/main.py` gốc chỉ là shim
   `from src.backend.main import app` để `pytest tests/`/`uvicorn src.main:app` vẫn chạy
   được — xem `Makefile`, `tests/conftest.py`).
2. **Dialogue engine thật KHÔNG dùng `src/agents/graph.py`/LangGraph cho luồng đặt xe** —
   `src/backend/services/session_service.py::SessionService.process_message()` là một
   state machine tự viết tay (regex "từ X đến Y", state COLLECT_PICKUP → 
   COLLECT_DESTINATION → CONFIRM → BOOKED, xử lý `stt_confidence < 0.55` → đếm
   `failed_count`, `failed_count >= 2` → `handoff_triggered=True`). `src/agents/graph.py`
   chỉ còn dùng cho route `/chat` legacy ("kept for compatibility with the current test
   suite" — đọc đúng docstring trong `src/backend/api/routes/__init__.py`).
3. `SessionService.sessions` là **class attribute** (dict dùng chung mọi instance
   `SessionService()`) — gọi trực tiếp `SessionService()` từ module khác vẫn đọc/ghi
   đúng cùng state với các route REST, **không cần** gọi qua HTTP hay token auth (token
   auth chỉ nằm ở route handler `_user_id_from_header`, không nằm trong `SessionService`).
4. `SessionMessageDTO` đã có sẵn `source: Literal["TEXT","VOICE"]` và `stt_confidence` —
   backend **đã chủ động thiết kế để nhận input từ voice** qua đúng endpoint REST
   `POST /api/v1/sessions/{id}/messages`, không phải qua WebSocket.
5. `src/backend/api/routes/calls.py` có `WS /calls/{call_id}/stream` nhưng là **stub rỗng**
   (accept → gửi "connected" → close ngay) và `CallService.create_call()` tạo
   `session_id` ngẫu nhiên **không hề gọi `SessionService.create_session()`** — session đó
   sẽ không tồn tại thật. Đây là code chưa hoàn thiện của người khác — **KHÔNG sửa file
   này** (rủi ro đụng vào việc người khác đang làm dở). Dùng path WS riêng cho Voice
   (`/api/v1/voice/stream`), không đụng `/calls/{call_id}/stream`.
6. `src/backend/integrations/asr_client.py`/`tts_client.py` là stub rỗng thật sự
   (`return ""`/`return b""`, không ai gọi tới) — an toàn để lấp đầy sau này nhưng
   **không bắt buộc cho tích hợp lần này** (Voice module tự chứa provider riêng, không
   phụ thuộc 2 file này).
7. `src/backend/config.py` (Settings riêng của backend) **không có field nào của Voice**
   — không thêm field vào file này (tránh đụng Settings người khác dùng).
8. Redis: cả `src/backend/integrations/redis_client.py` lẫn `SessionService` đều dùng
   in-memory, chưa ai thật sự dùng Redis — Voice cũng nên bỏ Redis cho lần tích hợp này
   (đơn giản hơn, khớp với thực tế hiện có, không phải quyết định kiến trúc treo nữa).

### Nguyên tắc tích hợp (bắt buộc tuân thủ)

- **File mới:** tự do thêm (`src/voice/`, `src/backend/api/routes/voice.py`,
  `tests/test_voice/`, `demo/`, `data/gazetteer/`, docs).
- **File người khác đã viết:** chỉ được đụng tối thiểu, thuần *additive*, và chỉ 3 file:
  1. `src/backend/main.py` — thêm 1 import + 1 dòng `app.include_router(...)` cho voice
     router (không đổi route nào đã có).
  2. `requirements.txt` — thêm block mới ở cuối, không sửa dòng nào đã có.
  3. `.env.example` — thêm block mới ở cuối, không sửa dòng nào đã có.
  Không sửa `.github/workflows/ci.yml`, không sửa bất kỳ file nào trong
  `src/backend/{api,controllers,services,schemas,models,integrations}/`,
  `src/agents/`, `src/frontend/`.
- **Dialogue state:** KHÔNG tự tạo state machine riêng trùng lặp với
  `SessionService` (tránh 2 nguồn sự thật). Voice Gateway gọi thẳng
  `SessionService()` (Python, cùng process) để tạo/dùng/kết thúc session — coi đây là
  "dialogue engine" duy nhất, y hệt cách Frontend đang dùng qua REST.
- **BR-001 (ngưỡng confidence cao hơn lúc xác nhận đặt xe):** `SessionService` chỉ có 1
  ngưỡng phẳng 0.55 cho mọi bước — không sửa `SessionService` để thêm ngưỡng riêng theo
  bước. Thay vào đó Voice Gateway tự thêm 1 lớp thận trọng phía client: nếu
  `current_step == "CONFIRM"` và confidence ASR thấp hơn ngưỡng cấu hình riêng của Voice
  (mặc định 0.80) → **không gửi lên backend**, tự phát lại câu hỏi xác nhận (không đụng
  `failed_count` của backend). Các bước khác gửi thẳng lên backend, tin tưởng ngưỡng 0.55
  của họ là nguồn quyết định duy nhất.
- **Bug hallucination-khi-im-lặng đã phát hiện ở phiên trước** (`utterance_rms()` +
  `is_known_hallucination()`) vẫn giữ nguyên — đây là an toàn ở tầng ASR, không liên quan
  gì tới backend, giữ lại y nguyên.

### Việc cần làm

1. Copy nguyên các module **không cần đổi logic** từ
   `C:\Users\KHANH\Documents\GitHub\P-160 copy\src\voice\` sang
   `C:\Users\KHANH\Documents\GitHub\P-160\src\voice\`:
   `audio/codec.py`, `audio/vad.py`, `asr/base.py`, `asr/confidence.py`,
   `asr/groq_provider.py`, `asr/biasing.py`, `tts/base.py`, `tts/edge_tts_provider.py`,
   `tts/formatter.py`, `tts/pronunciation.py`, `tts/cache.py`, `text/gazetteer.py`,
   `text/normalizer.py`. Copy `src/models/voice_schemas.py` — giữ `ASRResult`/`TTSResult`/
   `WSServerEvent`/`WSClientControl`/`WSEventType`/`ClientControlType`/`TurnStage`; có thể
   bỏ bớt các field/class liên quan session-state trùng backend nếu không dùng nữa
   (`VoiceSession`, `SessionStatus`, `HandoffReason` cũ) — tuỳ khi code thấy còn cần hay
   không, không bắt buộc xoá nếu giữ không hại gì.
2. **Viết mới** `src/voice/config.py` — `VoiceSettings(BaseSettings)` riêng, đọc cùng
   `.env` nhưng **không đụng** `src/backend/config.py`. Field tối thiểu: `groq_api_key`,
   `voice_asr_model`, `voice_asr_language`, `voice_tts_voice`, `voice_tts_rate`,
   `voice_vad_backend`, `voice_vad_silence_ms`, `voice_vad_sample_rate`,
   `voice_asr_confidence_threshold` (ngưỡng client-side riêng cho bước CONFIRM, mặc định
   0.80), `voice_min_utterance_rms`.
3. **Viết mới** `src/voice/session_bridge.py` thay cho `agent_bridge.py` cũ — bọc
   `SessionService`: `start(user_id, channel="WEB_VOICE", device_id=None)`,
   `send_message(session_id, text, stt_confidence) -> {action, message, state, booking}`,
   `get_session(session_id) -> dict`, `end(session_id, reason)`. Tự tạo `user_id` dạng
   `f"voice_guest_{uuid4().hex[:8]}"` cho mỗi cuộc gọi ẩn danh (không cần đăng nhập thật).
4. **Viết lại** `src/voice/gateway.py` (bỏ Redis, bỏ `SessionManager`/`ConfidenceGate`
   full BR-003, bỏ `agent_bridge`) theo pipeline mới:
   `audio chunk → codec resample → EndpointScorer → utterance_rms/hallucination guard →
   GroqASRProvider (+ gazetteer prompt_hint) → [nếu current_step=="CONFIRM" và confidence
   thấp: tự re-prompt, không gửi backend] → session_bridge.send_message() →
   formatter+pronunciation → EdgeTTSProvider (qua CachingTTSProvider) → audio trả về`.
   State theo dõi mỗi kết nối WS chỉ cần 1 dict nhẹ trong RAM (session_id, stage,
   resampler, endpoint scorer) — không cần persist qua restart (đúng thực tế
   `SessionService` cũng in-memory).
5. **Viết mới** `src/backend/api/routes/voice.py` — WS route `/api/v1/voice/stream` theo
   đúng protocol JSON/binary đã định nghĩa trong `voice_schemas.py` (giữ nguyên từ bản cũ,
   không đổi để `demo/demo.js` không cần sửa). Đăng ký thêm `GET /api/v1/voice/health`.
6. **Sửa tối thiểu** `src/backend/main.py`: thêm
   `from src.backend.api.routes.voice import router as voice_router` +
   `app.include_router(voice_router, prefix="/api/v1/voice", tags=["voice"])`; mount
   `/demo` static (copy đúng cách đã làm ở bản cũ, dùng `Path(__file__).resolve()` tính từ
   `src/backend/main.py` cho đúng, vì file này nằm sâu hơn 1 cấp so với `src/main.py` cũ).
7. Copy `demo/`, `data/gazetteer/place_names.json` nguyên trạng.
8. Copy + viết lại test trong `tests/test_voice/` — giữ nguyên test cho
   `codec/vad/confidence/groq_provider/gazetteer/biasing/normalizer/edge_tts_provider/
   formatter/pronunciation/cache` (không đổi logic, không cần sửa). Viết lại
   `test_gateway.py`/`test_voice_routes.py`/`fake_providers.py` cho kiến trúc mới (mock
   `SessionService`/`session_bridge` thay vì `agent_bridge`). Đặt `client` fixture theo
   đúng convention có sẵn trong `tests/conftest.py` (`from src.main import app`,
   `ASGITransport`) — không tạo conftest riêng nếu dùng chung được.
9. Thêm block mới cuối `requirements.txt`: `numpy`, `rapidfuzz`, `edge-tts`, (comment sẵn
   `onnxruntime`) — **không** thêm `redis` (đã bỏ dùng ở tích hợp này).
10. Thêm block mới cuối `.env.example`: các biến `VOICE_*`/`GROQ_API_KEY` (bỏ
    `REDIS_URL`/`VOICE_SESSION_TTL_SECONDS` vì không dùng nữa).
11. Copy toàn bộ docs Voice AI đã có sang, viết lại `docs/mustdo_voice.md` phản ánh đúng
    kiến trúc tích hợp mới (đặc biệt: xoá mục "xung đột kiến trúc session Voice/Backend"
    cũ — giờ đã giải quyết bằng cách dùng thẳng `SessionService`; ghi rõ giới hạn:
    `SessionService.process_message()` hiện là rule-based đơn giản, không phải LLM/Core
    Agent thật, nên hội thoại sẽ khá cứng — đây là giới hạn của chính backend, không phải
    của Voice).
12. Chạy `pytest tests/ -v` (toàn repo, không chỉ `tests/test_voice`) và
    `ruff check src/ tests/` — phải xanh 100%, đặc biệt **các test cũ của
    `tests/test_agents/` và `tests/test_api/` không được có test nào đỏ thêm** (bằng
    chứng "không ảnh hưởng gì tới BE/FE/agentic").

### Việc KHÔNG làm (ghi vào `mustdo_voice.md` nếu chưa xong)

- Không sửa `src/backend/api/routes/calls.py` dù đó rõ ràng là chỗ dở dang — không phải
  việc của Voice, để nguyên cho người phụ trách phần đó.
- Không lấp `asr_client.py`/`tts_client.py` (stub) trong lần này — ghi chú lại là có thể
  làm sau nếu team muốn, không tự quyết định thay.
- Không sửa `src/agents/` — Voice không dùng LangGraph agent trong kiến trúc tích hợp
  này (đã xác nhận thực tế dialogue engine là `SessionService`).
- Không merge/xoá `feature/voice-ai` — nhánh đó và `C:\...\P-160 copy` vẫn là bản lưu
  gốc, không đụng.
