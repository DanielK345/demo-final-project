# Tiến trình — Voice AI cho AloSM (tóm tắt toàn bộ phiên làm việc)

**Vai trò tài liệu:** Tóm tắt lại **toàn bộ** những gì đã làm trong phiên làm việc dài
với Claude về Voice AI, để đọc lại (người hoặc AI phiên sau) hiểu ngay được bối cảnh,
quyết định, và đặc biệt là **các bug tinh vi đã tìm ra** mà không cần đọc lại toàn bộ
lịch sử chat. Viết lúc chuẩn bị compact conversation.

**Ngày:** 2026-08-12 → 2026-08-13. **Trạng thái cuối:** 208/208 test pass, `ruff` sạch,
đã tích hợp xong vào project thật, đã fix 4 bug thật phát hiện qua test tay với server
đang chạy (không chỉ unit test).

---

## 0. Bối cảnh dự án

AloSM Voice AI — capstone/đồ án tốt nghiệp (KHÔNG phải sản phẩm thương mại), 4 người
làm chung, chia 8 phần công việc. Mục tiêu: demo đặt xe bằng giọng nói qua trình duyệt.
Ngân sách ~$0 — chỉ dùng API free tier (Groq Whisper, Edge-TTS).

Tài liệu gốc của team (đọc để hiểu yêu cầu, không sửa):
- `docs/voice-ai/voice_ai_overview.md` — kiến trúc, tech stack, 8 phần việc, business rules
  (BR-001 xác nhận trước khi đặt xe, BR-002 không tự suy diễn, BR-003 2 lần ASR fail →
  handoff).
- `docs/voice-ai/voice_todo_list.md` — chi tiết task/branch theo tuần.

---

## 1. Có 2 thư mục — PHẢI phân biệt rõ

| Thư mục | Branch | Vai trò |
|---|---|---|
| `C:\Users\KHANH\Documents\GitHub\P-160` | `feature/backend-data` | **Project thật đang dùng** — có Backend/Frontend/Agentic thật của team, giờ đã tích hợp Voice AI vào đây. Đây là nơi làm việc chính hiện tại. |
| `C:\Users\KHANH\Documents\GitHub\P-160 copy` | `feature/voice-ai` | **Bản backup** của Voice AI bản đầu (Phần 1-8) build trên project skeleton (chưa có BE/FE/agentic thật). Dùng làm nguồn tham chiếu khi copy module sang project thật. Không đụng vào nữa trừ khi cần đối chiếu. |

---

## 2. Timeline — đã làm gì, theo thứ tự

### Giai đoạn A — Build Voice AI trên project skeleton (`P-160 copy`, nhánh `feature/voice-ai`)

Làm theo đúng 8 phần trong `voice_ai_overview.md` (tự tạo prompt cho từng phần rồi tự
thực thi — xem `docs/prompt_voice_phan3_4.md`, `docs/prompt_voice_phan5_8.md` trong
`P-160 copy` nếu cần đọc lại chi tiết):

- **Phần 1** (Audio/VAD): `audio/codec.py` (resample PCM16 streaming), `audio/vad.py`
  (`EnergyVAD` + `SileroVAD` khung sẵn + `EndpointScorer` ngưỡng im lặng 900ms).
- **Phần 2** (Session/Gateway): schema `voice_schemas.py`, `session.py`, `gateway.py`
  (bản đầu — sau này viết lại hoàn toàn ở Giai đoạn C).
- **Phần 3** (ASR Core): `asr/groq_provider.py` (Groq Whisper qua httpx trực tiếp,
  không cần SDK), `asr/confidence.py`.
- **Phần 4** (ASR Quality): `text/gazetteer.py`, `asr/biasing.py` (fuzzy correction),
  `text/normalizer.py`.
  - **Bug tự phát hiện #1:** thuật toán fuzzy-match ban đầu so khớp mờ trên **cả cụm từ
    nối lại** → câu đã đúng sẵn bị "sửa" nhầm (nuốt mất 1 từ hàng xóm). Sửa bằng cách so
    khớp **theo từng từ một, đúng vị trí**, lấy điểm thấp nhất — 1 từ lạc lõng sẽ kéo
    điểm xuống thấp, bị loại ngay.
- **Phần 5** (TTS Core): `tts/edge_tts_provider.py`.
- **Phần 6** (TTS Quality): `tts/formatter.py` (số → chữ đọc, bộ chuyển đổi số tiếng
  Việt đầy đủ trăm/nghìn/triệu/thập phân), `tts/pronunciation.py` (override phát âm
  brand), `tts/cache.py` (`CachingTTSProvider`).
- **Phần 7** (Demo UI): `demo/index.html`, `demo/demo.js`, `demo/pcm-worklet.js` —
  WebSocket client, capture mic qua `AudioWorklet`.
- **Phần 8** (CI/CD, test): mở rộng `ci.yml`, `fake_providers.py`.

### Giai đoạn B — Có `GROQ_API_KEY` thật, verify + fix bug an toàn

Người dùng cung cấp Groq API key thật → set vào `.env` (không track git). Verify bằng
round-trip thật (edge-tts tạo audio → ffmpeg decode → `GroqASRProvider` thật):

- **Bug thật #2 (quan trọng, liên quan an toàn):** audio **im lặng hoàn toàn** khiến
  Whisper **hallucinate** ra hẳn 1 câu hoàn chỉnh ("Hãy subscribe cho kênh Ghiền Mì
  Gõ...") kèm **confidence CAO** (`no_speech_prob=0`, `avg_logprob≈-0.08` — Whisper "tự
  tin" với câu nó bịa). Nghĩa là confidence-gate thông thường **không chặn được** case
  này. Sửa bằng **2 lớp phòng thủ**:
  1. `utterance_rms()` (`audio/codec.py`) + `voice_min_utterance_rms` — tính năng lượng
     cả utterance, **không gọi ASR** nếu quá nhỏ (tránh tốn request + tránh rủi ro này).
  2. `is_known_hallucination()` (`asr/groq_provider.py`) — chặn cứng câu bịa cụ thể đã
     gặp (verify: Whisper bịa **y hệt câu này** mỗi lần với audio im lặng — deterministic
     vì Groq gọi Whisper với `temperature=0`).

### Giai đoạn C — Tích hợp thật vào project có BE/FE/Agentic (đang ở đây)

Người dùng copy Voice AI sang `P-160 copy` (backup), rồi chuyển `P-160` gốc sang nhánh
`feature/backend-data` (có Backend/Frontend/Agentic thật). Yêu cầu: tích hợp Voice AI
vào mà **không ảnh hưởng gì việc người khác đã làm**.

**Khảo sát code thật trước khi động tay (rất quan trọng — đảo ngược giả định ban đầu):**
- `src/backend/main.py` là app thật (`src/main.py` gốc chỉ là shim
  `from src.backend.main import app`).
- **Dialogue engine thật KHÔNG dùng `src/agents/` (LangGraph)** — mà là
  `src/backend/services/session_service.py::SessionService.process_message()`, một state
  machine rule-based tự viết tay (regex trích "từ X đến Y", state COLLECT_PICKUP →
  CONFIRM → BOOKED, tự xử lý `stt_confidence < 0.55` → đếm `failed_count` → handoff sau
  2 lần, y hệt tinh thần BR-003 nhưng code riêng). `src/agents/graph.py` chỉ còn phục vụ
  route `/chat` legacy.
- `SessionService.sessions` là **class attribute** — gọi `SessionService()` trực tiếp
  bằng Python (không qua HTTP/token auth) vẫn đọc/ghi đúng chung state với route REST.
- `SessionMessageDTO` đã có sẵn `source: "VOICE"` + `stt_confidence` — backend **đã chủ
  động thiết kế sẵn** để nhận input giọng nói qua REST `/sessions/{id}/messages`.

**Quyết định kiến trúc (ghi trong `docs/voice-ai/prompt_voice_integration_real_be_fe.md`):**
Voice Gateway gọi thẳng `SessionService` làm dialogue engine duy nhất — **bỏ hẳn**
Redis + LangGraph agent + state machine BR-003 riêng của Voice (tránh 2 nguồn sự thật).

**File mới/viết lại:**
- `src/voice/config.py` — `VoiceSettings` **tách riêng** khỏi `src/backend/config.py`
  (không đụng Settings của Backend).
- `src/voice/session_bridge.py` — **seam duy nhất** gọi `SessionService` thật (thay cho
  `agent_bridge.py` cũ gọi LangGraph).
- `src/voice/gateway.py` — **viết lại hoàn toàn**: bỏ Redis/SessionManager/ConfidenceGate
  đầy đủ, giữ lại `utterance_rms` gate + hallucination guard (an toàn ASR, không liên
  quan dialogue state), thêm 1 ngưỡng confidence riêng (0.80) **chỉ áp dụng thêm** ở bước
  CONFIRM (BR-001) làm lớp thận trọng phía client, mọi bước khác tin ngưỡng 0.55 phẳng
  của `SessionService`.
- `src/backend/api/routes/voice.py` — **file mới**, route WS `/api/v1/voice/stream` +
  REST `POST /speak` (thêm sau, xem Giai đoạn E) + `GET /health`.
- Copy nguyên (không đổi logic): `audio/*`, `asr/base.py`, `asr/confidence.py`,
  `asr/groq_provider.py`, `asr/biasing.py`, `tts/*`, `text/*`, `demo/*`,
  `data/gazetteer/place_names.json`, `src/models/voice_schemas.py`.

**Chỉ đụng 3 file của người khác, đều thuần additive:**
`src/backend/main.py` (thêm import + `include_router` cho voice router + mount
`/demo` static), `requirements.txt` (thêm block cuối file), `.env.example` (thêm block
cuối file). **Không sửa** route/controller/service/schema nào của Backend, không sửa
`src/agents/`, không sửa `src/frontend/` (ở giai đoạn này).

**Verify thật:** kết nối WebSocket thật (không mock) → audio giả → VAD → Groq ASR thật
→ gửi thẳng `SessionService` thật → nhận đúng câu trả lời thật → Edge-TTS thật. Bug #2
(hallucination) tái hiện đúng như dự đoán trong lần test này (audio test là tiếng "ù"
đều đều) và bị chặn đúng bởi 2 lớp phòng thủ đã có.

### Giai đoạn D — Chỉnh giọng đọc theo phản hồi thật (nghe bằng tai)

Người dùng nghe thử, phản hồi "giọng đọc bị robot":
- **Tìm ra:** `voice_tts_rate=0.9` (chậm 10%) làm giọng neural TTS nghe "đơ". Đổi mặc
  định về `1.0` (tốc độ gốc) trong `src/voice/config.py`, `.env.example`, `.env`.
- Tạo audio mẫu thật (không thể tự nghe — AI không có khả năng nghe) để người dùng tự
  so sánh, họ chọn cấu hình `rate=1.0` + giữ nguyên phần phiên âm thương hiệu
  (`pronunciation.py`: "AloSM"→"Alo Ét Em", "Landmark 81"→"Len Mác Tám Mươi Mốt") — xác
  nhận qua so byte audio (36864 bytes) khớp giữa live pipeline và mẫu đã duyệt.

### Giai đoạn E — Debug "Failed to fetch" khi đăng nhập → tìm ra bug chặn server thật

- **Bug thật #3 (nghiêm trọng):** `prewarm_tts_cache()` (gọi Edge-TTS 3 lần lúc khởi
  động để cache câu tĩnh) được `await` **trực tiếp** trong `lifespan` của
  `src/backend/main.py` → mất **~15-18 giây**, và trong suốt thời gian đó **uvicorn
  không hề mở cổng 8000** (verify bằng `netstat` — port hoàn toàn không listening).
  Browser gọi vào đúng lúc này → "Failed to fetch". Với `--reload` bật, mỗi lần sửa file
  là 1 cửa sổ "chết" ~15s.
  - **Fix:** đổi `await prewarm_tts_cache()` → `asyncio.create_task(prewarm_tts_cache())`
    (chạy nền, không chặn startup). Verify: trước fix mất 15-18s mới trả lời `curl`, sau
    fix trả lời **ngay <1s**.

### Giai đoạn F — Phát hiện `AssistantPage.tsx` dùng giọng đọc RIÊNG (browser API)

Người dùng phản hồi "giọng lúc đàn ông, đọc robot, lúc Anh lúc Việt":
- **Tìm ra:** `src/frontend/src/pages/Assistant/AssistantPage.tsx` (trang React thật)
  dùng **`window.speechSynthesis`** (TTS có sẵn của trình duyệt/OS) — hoàn toàn tách
  biệt khỏi pipeline Groq+Edge-TTS đã build và được duyệt! Cũng dùng
  `webkitSpeechRecognition` cho input (chưa đụng, ngoài phạm vi lần này).
- **Fix:**
  1. Thêm `POST /api/v1/voice/speak` (`src/backend/api/routes/voice.py`) — text vào,
     audio thật ra qua đúng pipeline đã tune (Edge-TTS + formatter + pronunciation).
  2. Sửa `speak()` trong `AssistantPage.tsx` gọi endpoint trên, phát qua `<audio>`,
     `window.speechSynthesis` chỉ còn làm **fallback** khi mất mạng.
  3. Tiện sửa luôn 1 bug TypeScript có sẵn không liên quan trong
     `src/frontend/src/app/config/api.ts` (`ApiError` dùng cú pháp parameter-property
     không hợp lệ với `erasableSyntaxOnly` — chặn `tsc -b` của cả frontend) — phát hiện
     khi cố verify `tsc -b` cho thay đổi của mình, sửa luôn vì đang chặn.

### Giai đoạn G — Đọc lẫn dấu câu, bug thứ tự pipeline

Người dùng phản hồi "đọc cả dấu phẩy ngoặc kép":
- Câu trả lời thật của `SessionService` có chứa dấu ngoặc kép cong (`"Đúng"`,
  `"Thôi"`) và dấu gạch chéo (`Anh/chị`) — Edge-TTS đọc các ký tự này thành lời theo
  nghĩa đen.
- **Fix:** thêm `sanitize_for_speech()` (`tts/formatter.py`) — bỏ ngoặc kép (thẳng lẫn
  cong), đổi `/` thành khoảng trắng. Thêm xử lý ký hiệu tiền tệ `₫` → " đồng" (trong
  `format_for_speech`).
- **Bug thật #4 (quan trọng nhất trong đợt này) — tự phát hiện qua chính test mình
  viết:** `format_for_speech` (đổi số→chữ) chạy **trước** `apply_pronunciation_overrides`
  trong `gateway.py::_speak()` → với câu thật "...từ Landmark 81 đến..." (số theo sau là
  khoảng trắng, không phải dấu chấm), formatter đổi "81"→"tám mươi mốt" **trước khi**
  pronunciation kịp khớp chuỗi gốc "Landmark 81" để đổi thành "Len Mác Tám Mươi Mốt" —
  **mất tác dụng của phần phát âm đã được duyệt ở Giai đoạn D** (vì mẫu test hồi đó
  tình cờ có dấu chấm ngay sau số, né được bug). **Sửa:** đổi thứ tự cố định trong
  `gateway.py::_speak()` — pronunciation **luôn chạy trước** formatter (có comment giải
  thích rõ lý do ngay trong code, tránh ai đổi lại nhầm).
- Verify bằng đúng câu `SessionService._confirm()` sẽ nói qua server thật — kết quả
  đúng hoàn toàn.

---

## 3. Bug quan trọng — tổng hợp lại để không lặp lại

| # | Bug | File | Đã sửa bằng |
|---|---|---|---|
| 1 | Fuzzy-match "ăn" nhầm từ hàng xóm | `asr/biasing.py` | So khớp theo từng từ, lấy điểm thấp nhất |
| 2 | Whisper hallucinate khi im lặng, confidence CAO | `asr/groq_provider.py`, `gateway.py` | `utterance_rms()` gate + `is_known_hallucination()` |
| 3 | `prewarm_tts_cache()` chặn server khởi động ~15-18s (port không listening) | `src/backend/main.py` | `asyncio.create_task()` thay vì `await` |
| 4 | `format_for_speech` chạy trước `pronunciation`, "ăn" mất số trong tên riêng | `gateway.py::_speak()` | Đổi thứ tự: pronunciation → formatter |

**Bài học chung:** cả 4 bug đều KHÔNG lộ ra qua unit test đơn lẻ ban đầu — chỉ lộ ra khi
test với dữ liệu/kịch bản THẬT (API key thật, server thật đang chạy, câu trả lời thật
của `SessionService`, nghe/verify bằng tay). Khi sửa thêm bất kỳ phần TTS/ASR nào sau
này, nên verify bằng round-trip thật (script trong lịch sử chat có mẫu, dùng
`edge_tts`/`ffmpeg`/gọi thẳng server đang chạy), không chỉ tin unit test mock.

---

## 4. Trạng thái hiện tại

- **208/208 test pass** (`pytest tests/ -v` từ `C:\Users\KHANH\Documents\GitHub\P-160`),
  `ruff check src/ tests/` sạch cho toàn bộ file Voice AI.
- `tsc -b --noEmit` sạch cho frontend (kể cả sau khi sửa `AssistantPage.tsx` + `api.ts`).
- Server chạy thật ở `http://localhost:8000` — khởi động tức thì (đã fix bug #3),
  `/api/v1/voice/health`, `/api/v1/voice/stream` (WS), `/api/v1/voice/speak` (REST) đều
  hoạt động, verify bằng request thật.
- `.env` đã có `GROQ_API_KEY` thật (không track git), `VOICE_TTS_RATE=1.0`.
- `AssistantPage.tsx` giờ dùng giọng đọc thật (Edge-TTS qua `/speak`), không còn
  `window.speechSynthesis` làm đường chính.

## 5. Việc còn lại (xem đầy đủ trong `docs/voice-ai/mustdo_voice.md`, phần này có thể hơi cũ vì
viết trước Giai đoạn D-G — ưu tiên đọc file `tientrinh.md` này trước)

- Chưa test bằng **mic + loa người thật** qua `demo/index.html` hoặc `AssistantPage.tsx`
  (mọi verify ở trên đều qua script/`TestClient`, chưa ai bấm mic thật nói vào).
- Microphone input ở `AssistantPage.tsx` vẫn dùng `webkitSpeechRecognition` của trình
  duyệt (chưa đổi sang Groq ASR) — chỉ mới sửa phần giọng đọc RA, chưa sửa phần nghe VÀO.
- Silero VAD chưa test model `.onnx` thật (đang dùng `EnergyVAD` mặc định).
- `data/gazetteer/place_names.json` vẫn là 23 địa danh seed, chưa phải danh sách thật
  AloSM.
- `SessionService` là rule-based đơn giản (không phải LLM thật) — hội thoại còn cứng,
  đây là giới hạn của Backend, không phải của Voice.
- Chưa push code lên remote / chưa chạy CI thật (`.github/workflows/ci.yml`) với các
  thay đổi này.
- 2 branch (`feature/backend-data` đang dùng, `feature/voice-ai` ở `P-160 copy`) chưa
  được merge/hợp nhất chính thức — vẫn để riêng theo đúng yêu cầu ban đầu.

## 6. Cách chạy/test nhanh (nếu cần verify lại sau compact)

```bash
cd "C:\Users\KHANH\Documents\GitHub\P-160"
.venv/Scripts/python.exe -m pytest tests/ -q        # 208 test, không gọi API thật
.venv/Scripts/python.exe -m ruff check src/ tests/
.venv/Scripts/python.exe -m uvicorn src.main:app --host 0.0.0.0 --port 8000
# mở http://localhost:8000/demo/ (Chrome/Edge) hoặc chạy frontend thật (src/frontend, npm run dev)
```
