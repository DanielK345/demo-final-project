# Voice AI — Must-do (việc tôi KHÔNG làm được / cần người tự hoàn thiện)

**Vai trò tài liệu:** Đi kèm với việc **tích hợp Voice AI vào project thật** (có
Backend/Frontend/Agentic của team, nhánh `feature/backend-data`) — xem
[prompt_voice_integration_real_be_fe.md](prompt_voice_integration_real_be_fe.md) cho
prompt/kiến trúc tích hợp đầy đủ, [voice_ai_overview.md](voice_ai_overview.md) cho bối
cảnh/quyết định kỹ thuật ban đầu (một phần đã thay đổi khi tích hợp thật, xem cảnh báo
đầu file đó). File này liệt kê: đã verify được gì bằng dữ liệu thật, và việc gì còn cần
người làm tiếp.

**Cập nhật:** 2026-08-12 (phiên tích hợp vào project thật)

---

## 0. Đã xong — verify bằng chạy thật, không chỉ unit test

- **196/196 test pass** (`pytest tests/ -v` từ repo root) — gồm **76 test cũ của
  `tests/test_agents/`+`tests/test_api/` (Backend/Agentic) vẫn xanh nguyên**, chứng
  minh việc tích hợp không phá gì đã có. `ruff check` sạch cho toàn bộ file Voice mới
  tạo (4 lỗi E402 còn lại trong `src/backend/main.py` là **lỗi có sẵn từ trước** do
  cách file đó tự thêm `PROJECT_ROOT` vào `sys.path` trước khi import — không phải lỗi
  do Voice AI gây ra, xem lịch sử file).
- **Đã tự chạy thử WS end-to-end thật** qua `TestClient` (không phải chỉ mock): audio
  giả → VAD → ASR thật (Groq, có `GROQ_API_KEY` thật trong `.env`) → **gửi thẳng lên
  `SessionService` thật của Backend** → nhận lại đúng câu trả lời thật của
  `SessionService` ("Em chưa nghe rõ. Anh/chị vui lòng nói lại...") → TTS thật
  (Edge-TTS, 38KB audio mp3 thật). Chứng minh toàn bộ chuỗi tích hợp hoạt động, không
  chỉ là lý thuyết.
- **Bug hallucination-khi-im-lặng** (Whisper bịa câu khi audio không phải tiếng nói
  thật — phát hiện ở phiên làm việc trước) **tái hiện đúng như dự đoán** trong lần
  chạy thử này (audio test là tiếng "ù" đều đều, không phải giọng nói thật) — và được
  chặn đúng bởi `is_known_hallucination()` (confidence ép về 0.0), sau đó
  `SessionService` tự xử lý đúng theo logic thất bại nhận dạng của chính nó. Xác nhận
  cơ chế 2 lớp phòng thủ (RMS gate + hallucination blocklist) vẫn hoạt động đúng trong
  bối cảnh tích hợp mới.
- **Đã đổi kiến trúc quan trọng so với bản gốc** (xem
  `prompt_voice_integration_real_be_fe.md` để biết lý do đầy đủ):
  - Bỏ `agent_bridge.py` (gọi `src/agents/graph.py`/LangGraph) → thay bằng
    `src/voice/session_bridge.py` (gọi thẳng
    `src.backend.services.session_service.SessionService` — dialogue engine THẬT đang
    chạy, không phải LangGraph agent legacy).
  - Bỏ Redis + `SessionManager`/`ConfidenceGate` tự quản dialogue state → dialogue
    state giờ do `SessionService` sở hữu duy nhất (tránh 2 nguồn sự thật).
  - Voice chỉ còn tự thêm 1 ngưỡng confidence riêng (0.80) ở đúng bước xác nhận đặt xe
    (BR-001) như lớp phòng thủ bổ sung phía client — mọi bước khác tin tưởng hoàn toàn
    ngưỡng 0.55 phẳng của `SessionService`.
- **File người khác đã đụng: chỉ 3 file, đều thuần additive** —
  `src/backend/main.py` (1 block import + 2 dòng đăng ký router/mount static),
  `requirements.txt` (block mới cuối file), `.env.example` (block mới cuối file). Không
  sửa bất kỳ route/controller/service/schema nào của Backend, không sửa `src/agents/`,
  không sửa `src/frontend/`.

---

## 1. Việc CỐ TÌNH không làm — đã quyết định trong lúc tích hợp, ghi lại lý do

| Việc | Vì sao không làm |
|---|---|
| Sửa `src/backend/api/routes/calls.py` (`WS /calls/{call_id}/stream` đang là stub rỗng, `CallService.create_call()` tạo `session_id` không hề đăng ký với `SessionService`) | Rõ ràng là code dở dang của người khác — không phải việc của Voice, có thể người phụ trách đang làm tiếp. Sửa sẽ vi phạm nguyên tắc "không ảnh hưởng việc người khác". Voice dùng path riêng (`/api/v1/voice/stream`), không đụng file này. |
| Lấp `src/backend/integrations/asr_client.py`/`tts_client.py` (stub rỗng, không ai gọi) | An toàn để làm (không ảnh hưởng gì, đang trả `""`/`b""` vô điều kiện) nhưng **không bắt buộc** — Voice tự chứa provider riêng (`GroqASRProvider`/`EdgeTTSProvider`), không phụ thuộc 2 file này. Để lại cho team quyết định có muốn hợp nhất không. |
| Sửa `src/agents/` (Core Agent/LangGraph) | Đã xác nhận thực tế: dialogue engine thật của F1 (đặt xe) là `SessionService`, không phải LangGraph agent (agent chỉ còn phục vụ `/chat` legacy). Không có lý do để đụng vào. |
| Sửa `.github/workflows/ci.yml` | Không cần — `requirements.txt` đã update nên `pip install -r requirements.txt` trong CI tự động cài đủ dependency mới (numpy/rapidfuzz/edge-tts), không cần đổi gì trong workflow. |
| Merge/xoá nhánh `feature/voice-ai` hay thư mục backup `C:\...\P-160 copy` | Không phải việc của tôi tự quyết — đó vẫn là bản lưu gốc, giữ nguyên. |

---

## 2. Giới hạn thật của `SessionService` (không phải giới hạn của Voice)

`SessionService.process_message()` — dialogue engine mà Voice đang dùng — là **rule-based
đơn giản** (regex trích "từ X đến Y", state machine cứng COLLECT_PICKUP → CONFIRM →
BOOKED), **không phải LLM/Core Agent thật**. Nghĩa là:

- Hội thoại sẽ khá cứng, chỉ hiểu đúng mẫu câu đã lập trình sẵn (vd. "đặt xe từ A đến
  B", "đúng"/"thôi" để xác nhận) — nói khác đi có thể không được hiểu.
- Đây là giới hạn của chính Backend hiện tại, **không phải lỗi tích hợp của Voice** —
  khi nào Backend nâng cấp `SessionService` lên dùng Core Agent/LLM thật, Voice
  **không cần sửa gì** (nhờ `session_bridge.py` là seam duy nhất, đã cô lập đúng chỗ).

---

## 3. Chưa test được — cần người làm tiếp

| Việc | Vì sao chưa làm |
|---|---|
| **Test qua demo UI bằng mic/loa thật** (`http://localhost:8000/demo/`) | Mọi verify ở trên đều qua `TestClient`/script Python, chưa ai bấm "Gọi" và nói vào mic trình duyệt thật qua kiến trúc tích hợp mới này. Việc dễ nhất, giá trị cao nhất, nên làm ngay. |
| Test giọng người thật đa dạng (vùng miền, nói nhỏ) | `voice_min_utterance_rms=0.01` mới hiệu chỉnh bằng audio tổng hợp (xem lịch sử `mustdo_voice.md` cũ trong `feature/voice-ai`) — chưa test với giọng người thật qua đường tích hợp mới. |
| Silero VAD với model `.onnx` thật | Vẫn dùng `EnergyVAD` mặc định — chưa đổi. |
| Danh sách địa danh thật (`data/gazetteer/place_names.json`) | Vẫn là 23 địa danh seed, chưa phải danh sách thật AloSM. |
| `AuthService._auth_response` luôn tạo session `channel="WEB_VOICE"` bất kể đăng nhập từ đâu (đọc thấy khi khảo sát code, không phải Voice gây ra) | Không phải việc của Voice — ghi lại để team Backend biết nếu cần sửa. |
| CI thật (GitHub Actions) chưa chạy thử với thay đổi này | Chỉ mới chạy `pytest`/`ruff` local — chưa push để CI thật xác nhận (cần push code trước). |

---

## 4. Gợi ý thứ tự làm tiếp

1. **Test tay qua demo UI thật** (mic + loa người thật) — `uvicorn src.main:app --reload`
   (hoặc `make run`), mở `http://localhost:8000/demo/`.
2. Thử các mẫu câu THẬT mà `SessionService` hiểu được (xem
   `src/backend/services/session_service.py` để biết chính xác từ khoá/mẫu câu) — vd.
   "tôi muốn đặt xe", "từ Vincom Đồng Khởi đến Landmark 81", "đúng", "thôi".
3. Push code, xác nhận CI (`.github/workflows/ci.yml`) chạy xanh với dependency mới.
4. Bổ sung danh sách địa danh thật vào gazetteer (giúp `SessionService`'s
   `_extract_route()` regex + Voice's ASR nhận đúng tên hơn).
5. Bàn với team Backend về `calls.py` stub và `asr_client.py`/`tts_client.py` — có
   muốn hợp nhất với module Voice hay giữ tách biệt như hiện tại.
6. Khi Backend nâng cấp `SessionService` lên Core Agent/LLM thật — chỉ cần review lại
   `src/voice/session_bridge.py`, không cần sửa `gateway.py`/route.
