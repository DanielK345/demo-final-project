# Kế hoạch giảm latency AloSM Voice

> **Trạng thái: LEGACY_REFERENCE.** Tài liệu này phân tích REST voice pipeline cũ,
> không mô tả LiveKit runtime hiện tại. Kế hoạch đo và tối ưu hiện hành nằm tại
> [`../PHASE4_EVALUATION_PLAN.md`](../PHASE4_EVALUATION_PLAN.md).

Cập nhật: **2026-08-16**

Trạng thái: **READY FOR IMPLEMENTATION — chưa phải bằng chứng đạt SLO production**
Phạm vi code: sau merge `origin/feature/backend-data` vào `feature/voice-ai` tại commit `81ad534`.

## 1. Kết luận audit

Latency cảm nhận hiện tại là tổng của một critical path gần như hoàn toàn tuần tự:

```text
VAD/endpoint silence
  -> đóng MediaRecorder + upload toàn bộ WebM
  -> STT (OpenAI/Gemini hoặc decode + queue + ZipFormer)
  -> normalize/gazetteer
  -> LLM transcript rewrite (tối đa 5 giây khi bật)
  -> Agent LLM (tối đa 5 giây mỗi lượt)
  -> 0..8 vòng Tool -> Agent
  -> content review
  -> TTS provider + retry/fallback + decode/validate toàn bộ audio
  -> base64 JSON (+ khoảng 33% kích thước so với binary)
  -> browser decode rồi mới phát
```

`POST /api/v1/voice/turn` chưa ghi timing theo từng stage, chưa trả `Server-Timing`, và frontend chưa ghi mốc từ lúc người dùng ngừng nói đến audio đầu tiên. Vì vậy chưa được tuyên bố một nguyên nhân duy nhất hoặc một p95 end-to-end “đã đo”. Việc đầu tiên là tạo baseline thật.

Các nút thắt có bằng chứng trực tiếp trong code:

| Nút thắt | Bằng chứng hiện tại | Tác động |
|---|---|---|
| Chờ endpoint | `VOICE_VAD_SILENCE_MS=900` | Cộng gần 0,9 giây trước khi request bắt đầu trong trường hợp thông thường. |
| Upload không streaming | Frontend chỉ gọi `sendVoiceTurn()` sau khi có cả `Blob` | Không chồng lấp upload với thời gian người dùng nói. |
| Hai LLM nối tiếp | `VoiceService`: transcript rewrite rồi `SessionService`; Agent có model call riêng | Một voice turn không-tool có thể trả hai lần network/model latency. Legacy Agent còn có contextual rewrite riêng nếu bật. |
| Tool loop tuần tự | `SessionService._MAX_TOOL_TURNS = 8`; mỗi tool result gọi Agent lại | Booking phức tạp có thể phát sinh nhiều model round-trip. |
| TTS phải xong toàn bộ | Orchestrator synthesize, validate bằng ffmpeg/NumPy rồi mới trả | Time-to-first-audio gần bằng toàn bộ thời gian tạo audio. |
| Audio base64 trong JSON | `audio_base64` trong `VoiceTurnResponse` | Tăng payload, copy bộ nhớ và thời gian parse/decode browser. |
| Client/provider chưa tái sử dụng đầy đủ | Gemini tạo `httpx.AsyncClient` mỗi request; voice client được build mỗi turn | Mất keep-alive/TLS reuse. |
| Logging đồng bộ | `ConversationLogger` đọc và ghi lại toàn bộ JSON bằng file I/O ngay trên request | Chặn event loop; chi phí tăng theo độ dài hội thoại. |
| Metrics rời rạc | ASR/TTS có metrics riêng, voice/agent/tool/frontend chưa có span chung | Không biết stage nào chi phối p95/p99 hoặc lỗi theo provider. |
| DB tương lai | Runtime Postgres dùng `NullPool` | Khi session chuyển sang durable store, mỗi transaction có thể chịu connect/TLS overhead; cần benchmark với Supavisor thay vì đoán. |

Bằng chứng có sẵn duy nhất đủ cụ thể là benchmark ZipFormer trong `docs/voice-ai/zipformer-asr.md`: audio 10 giây có p95 khoảng 188/278/518/1071 ms ở concurrency 1/2/4/8; toàn ma trận có max p95 11,704 giây. Đây là benchmark ASR, không phải latency của cuộc gọi end-to-end.

## 2. Mục tiêu kỹ thuật sơ bộ

Các số dưới đây là **engineering target để chạy thử**, cần Product/Ops ký duyệt thành SLO chính thức sau baseline staging:

| Chỉ số | Target ứng viên |
|---|---:|
| End-of-speech -> transcript final, warm, audio <=10 giây | p50 <= 0,8 s; p95 <= 1,5 s |
| Transcript final -> agent text, không tool | p50 <= 0,8 s; p95 <= 1,5 s |
| Agent text đã duyệt -> audio byte đầu tiên | p50 <= 0,6 s; p95 <= 1,2 s |
| End-of-speech -> audio byte đầu tiên, không tool | p50 <= 1,8 s; p95 <= 3,5 s |
| Turn có một read-only tool | p95 <= 5,5 s |
| Queue reject/error ở tải đã duyệt | < 1% |
| Safety/booking/critical-entity regression | 0 regression so với release gate hiện hành |

Không lấy timeout 5/12/30/45 giây làm SLO. Timeout chỉ là giới hạn lỗi, không phải latency chấp nhận được.

## 3. P0 — đo đúng trước khi tối ưu

### 3.1 Trace một voice turn xuyên suốt

Thêm `request_id`, `session_id`, `turn_id` và trace context xuyên frontend -> voice route -> STT -> rewrite -> agent -> tool -> TTS. ID chỉ xuất hiện trong log/event, không dùng làm Prometheus label.

Ghi các stage bằng `time.perf_counter()`:

- `endpoint_wait_ms` (frontend);
- `upload_ms` và `request_total_ms` (frontend);
- `asr_decode_ms`, `asr_queue_wait_ms`, `asr_inference_ms`, `asr_total_ms`;
- `normalize_ms`, `transcript_rewrite_ms`, `transcript_rewrite_outcome`;
- `agent_model_ms`, `agent_total_ms`;
- `tool_ms` theo `ToolName`, số vòng tool;
- `tts_queue_wait_ms`, `tts_provider_ms`, `tts_validate_ms`, `tts_total_ms`;
- `response_serialize_ms`, `browser_decode_ms`, `time_to_first_audio_ms`.

Các file đầu tiên cần sửa:

- `src/backend/api/routes/voice.py` — request timer, correlation và `Server-Timing`;
- `src/backend/services/voice_service.py` — stage spans;
- `src/backend/services/session_service.py` — agent/tool loop spans và số vòng;
- `src/agents/core/model.py`, `src/backend/services/transcript_rewriter.py` — provider duration/outcome;
- `src/voice/tts/orchestrator.py` — tách queue/provider/validator thay vì chỉ audio duration;
- `src/frontend/src/features/voice/api.ts` và `VoiceAssistantContext.tsx` — RUM từ recorder stop đến playback start.

Metric tối thiểu:

```text
voice_turn_duration_seconds{channel,provider,outcome}
voice_stage_duration_seconds{stage,provider,outcome}
voice_tool_rounds_total{tool,outcome}
voice_time_to_first_audio_seconds{channel,outcome}
voice_payload_bytes{direction,content_type}
```

Không ghi transcript, phone, địa chỉ, booking ID, session ID hoặc model output vào metric label. AI logs chỉ nhận duration, provider/model version, reason code và ID đã hash/correlation.

### 3.2 Baseline có thể tái lập

Tạo benchmark runner gọi API thật, xuất JSON/CSV gồm config snapshot, commit SHA, provider/model, warm/cold, audio duration, concurrency, từng stage và outcome. Ma trận tối thiểu:

- 100 turn không tool và 50 turn có tool;
- audio 2/5/10/20 giây;
- concurrency 1/4/8;
- warm và cold start;
- ZipFormer/OpenAI STT theo provider thực sự được chọn;
- transcript rewrite on/off/gated;
- TTS primary, fallback và cache hit/miss.

Acceptance không dùng mock/fake. Fixture phải có consent và ground truth; thiếu corpus/credential/SKU production tiếp tục theo `mustdo.md` mục 4, 5, 7, 8 và 9.

## 4. P0 — quick wins sau khi có baseline

### 4.1 Không gọi rewrite LLM cho mọi transcript

Thêm `TranscriptRewriteGate` trước `OpenAITranscriptRewriter`. Fast path giữ kết quả deterministic khi:

- transcript sạch, ngắn và không có token nghi ngờ;
- địa danh đã khớp gazetteer với confidence cao;
- câu chỉ là ordinal/yes/no/cancel có rule chắc chắn;
- đang ở bước xác nhận và không có dấu hiệu ASR sai.

Chỉ gọi LLM khi có tín hiệu lỗi chính tả/địa danh, confidence thấp, ambiguity hoặc critical entity cần chuẩn hóa. Ghi `gate_reason`; chạy false-correction/SER/CER/WER gate trước rollout.

Bắt buộc invariant: mỗi turn tối đa **một** semantic rewrite layer. `/voice/turn` không được chạy cả post-ASR rewrite và legacy contextual rewrite cho cùng transcript. Model-driven Agent vẫn nhận transcript đã chuẩn hóa, còn raw transcript được giữ để audit/safety.

### 4.2 Tái sử dụng connection và client

- Cache `OpenAIVoiceClient`, `AsyncOpenAI` và một `httpx.AsyncClient` theo lifespan; đóng ở shutdown.
- Bật keep-alive/HTTP2 khi provider hỗ trợ, đặt connect/read/write timeout riêng.
- Không tạo client mới trong mỗi `GeminiVoiceClient.transcribe()`.
- Đo DNS/connect/TLS/TTFB để xác nhận lợi ích; rollback về factory cũ nếu connection stale tăng lỗi.

### 4.3 Loại I/O đồng bộ khỏi event loop

`ConversationLogger` hiện đọc rồi ghi lại cả file JSON mỗi turn. Chuyển sang một trong hai hướng:

1. event append-only qua bounded async queue + worker; hoặc
2. durable conversation repository/Postgres với transaction ngắn.

Request chỉ chờ enqueue có giới hạn; queue full phải trả metric/error rõ, không âm thầm mất audit. Flush khi shutdown. Không dùng `asyncio.to_thread` không giới hạn như một “pool” giả.

### 4.4 Giảm payload mà chưa đổi protocol lớn

- Không trả cùng một audio hai lần; frontend chỉ gọi `/speak` nếu `/turn` không có audio hoặc playback thực sự lỗi.
- Đặt giới hạn response/audio bytes và đo serialization/base64 decode.
- Với typed turn, cho backend trả audio từ cùng TTS orchestrator hoặc một binary endpoint thống nhất, tránh thêm round-trip không cần thiết.

## 5. P1 — streaming và giảm model round-trip

### 5.1 Streaming transport

Chuyển frontend chính từ “record xong mới POST blob” sang WebSocket/giao thức streaming đã thống nhất:

1. gửi PCM/Opus frame 20–100 ms;
2. server VAD và ASR nhận dần;
3. phát `transcript.partial`, sau đó `transcript.final`;
4. trả `agent.text` ngay khi đã qua output review;
5. stream `audio.chunk` sau khi nội dung toàn câu/đoạn đã được kiểm duyệt.

Không stream audio trước safety/content review. Hỗ trợ backpressure, sequence number, reconnect và barge-in; không tạo hai pipeline state riêng giữa HTTP và WebSocket.

Giảm `VOICE_VAD_SILENCE_MS` chỉ sau ROC test trên corpus thật. Thử 350/500/700/900 ms, đo truncation và false endpoint; không hard-code 350 ms vì có thể cắt người nói chậm.

### 5.2 Time-to-first-audio

- TTS theo câu/đoạn ngắn đã duyệt, stream chunk đầu thay vì chờ toàn file.
- Giữ validation kỹ thuật trên từng segment và giới hạn số segment.
- Cache chỉ câu an toàn, không chứa PII/giá/địa chỉ/booking; key gồm normalized text, voice, rate, provider version và reviewer-policy version.
- Prewarm không chặn startup và không cạnh tranh với first user turn. Theo dõi trạng thái warm; ưu tiên một câu đại diện thay vì ba request tuần tự nếu benchmark chứng minh đủ.

### 5.3 Giảm vòng Agent/Tool

- Với tool result có reducer deterministic (place candidates, vehicle options, fare), cập nhật state bằng typed reducer và chỉ gọi model khi cần diễn đạt/ra quyết định ngữ nghĩa.
- Cho phép song song **chỉ** các read-only call độc lập đã biết đủ input; không song song booking/create/cancel hoặc các bước có dependency.
- Giới hạn tool budget theo loại turn thay vì chỉ `_MAX_TOOL_TURNS=8`; log lý do mỗi vòng và handoff an toàn khi vượt budget.
- Rút gọn context/prompt về cửa sổ cần thiết; đo token input/output và cache-hit của provider nếu có.

## 6. P1 — persistence và hạ tầng

Khi session chuyển từ memory sang Postgres:

- benchmark `NullPool` hiện tại với một pool app bounded qua Supavisor transaction mode;
- vẫn tắt prepared-statement cache theo contract hiện hành;
- đo acquire/connect/query/commit riêng, concurrency 1/8/32 và connection budget;
- chỉ đổi pool khi p95 giảm mà không gây connection exhaustion/stale connection.

Đặt service cùng region với DB và provider ưu tiên; đo network RTT trước khi đổi model. ZipFormer autoscale theo queue wait, RTF, CPU/RSS và reject rate, không chỉ theo request count.

## 7. P2 — load, quality và rollout

### Gate bắt buộc

1. Ruff, typecheck, pytest và frontend build pass.
2. Live STT/rewrite/Agent/TTS dùng provider thật; mock chỉ dùng unit test, không dùng làm acceptance evidence.
3. So sánh trước/sau trên cùng corpus và commit/config cố định.
4. Không tăng WER/CER, entity error, false correction, semantic flip, booking safety violation hoặc handoff miss quá ngưỡng đã duyệt.
5. Load test 30 phút và soak 4–8 giờ trên SKU staging gần production; theo dõi p50/p95/p99, error, queue, RSS/CPU, connection và cost.
6. Canary 5% -> 25% -> 50% -> 100%; rollback tự động khi latency/error/quality vượt gate.

### Rollback độc lập

Mỗi tối ưu có feature flag riêng:

- `VOICE_TRANSCRIPT_REWRITE_MODE=off|always|gated`;
- `VOICE_STREAMING_ENABLED`;
- `VOICE_TTS_STREAMING_ENABLED`;
- `VOICE_ASYNC_AUDIT_LOG_ENABLED`;
- `DATABASE_POOL_MODE=null|bounded`.

Không dùng một cờ tổng làm rollback cho mọi thay đổi.

## 8. Thứ tự triển khai đề nghị

| Thứ tự | Hạng mục | Kết quả phải giao |
|---:|---|---|
| 1 | Trace + `Server-Timing` + frontend RUM | Baseline JSON/CSV và dashboard stage p50/p95/p99. |
| 2 | Rewrite gate + chống double rewrite | Giảm model-call/turn, quality gate không regression. |
| 3 | Persistent HTTP/LLM clients + async audit sink | Giảm connect/I/O wait; queue có backpressure. |
| 4 | Tool-round budget + deterministic reducers | Giảm agent model call ở turn booking có tool. |
| 5 | Streaming upload/ASR và adaptive endpoint | Giảm end-of-speech -> transcript final. |
| 6 | Reviewed streaming TTS/binary audio | Giảm transcript final -> first audio. |
| 7 | DB pool bake-off + staging load/soak | Chọn config bằng số đo trên SKU thật. |
| 8 | Canary và ký SLO | Release report, owner, ngày, config và rollback evidence. |

## 9. Definition of Done

Kế hoạch chỉ hoàn tất khi có:

- trace đủ stage cho >=99% voice turn và không lộ PII;
- baseline và after-report tái lập được bằng command/version ghi rõ;
- p50/p95/p99 theo warm/cold, provider, audio length và concurrency;
- target/SLO được Product/Ops/SRE ký duyệt;
- quality/safety gates đạt trên corpus thật có consent;
- load/soak/canary pass, cost và capacity được chốt;
- runbook cảnh báo, rollback và post-incident query;
- mọi bằng chứng được link từ tài liệu hiện hành, không chỉ ghi “đã tối ưu”.
