# AloSM — Nghiên cứu refactor full sang LiveKit Agents

Cập nhật: **2026-08-17** · Trạng thái: **PROPOSED**

Implementation handoff đã chốt nằm tại
[`LIVEKIT_MIGRATION_IMPLEMENTATION.md`](./LIVEKIT_MIGRATION_IMPLEMENTATION.md). Khi
code, tài liệu implementation có thẩm quyền cao hơn các ví dụ/đề xuất trong tài liệu
nghiên cứu này.

## 1. Kết luận kiến trúc

AloSM nên refactor theo hướng **LiveKit-native cho toàn bộ Voice Agent runtime**:

```text
React LiveKit client
→ LiveKit Room / WebRTC
→ AgentServer
→ AgentSession
→ AloSM Agent / AgentTask
→ LiveKit function tools
→ AloSM application services
→ PostgreSQL hoặc fake integration
```

`Full LiveKit-native` trong tài liệu này có nghĩa là:

- dùng LiveKit cho media transport, room, audio track và session lifecycle;
- dùng `AgentSession` cho STT–LLM–TTS pipeline, turn handling và interruption;
- dùng `Agent`, `AgentTask`, chat context và `userdata` cho runtime hội thoại;
- dùng function tools/tool loop của LiveKit thay cho tool loop tự triển khai;
- dùng events, metrics, session report và testing API của LiveKit;
- chỉ viết custom code tại extension point chính thức của framework.

Nó **không** có nghĩa là không viết code riêng. LiveKit là framework tổng quát nên
không thể cung cấp sẵn luật đặt xe, schema booking, PII policy hoặc API của AloSM.
Các phần này vẫn phải tự xây, nhưng phải được đặt trong `Agent`, `AgentTask`, function
tool, hook và `userdata` mà LiveKit cung cấp; không dựng một framework song song.

## 2. Vì sao kiến trúc hiện tại cần thay

Repository hiện có hai voice runtime:

| Luồng | Transport | Provider | Client |
|---|---|---|---|
| `POST /api/v1/voice/turn` | upload cả utterance | OpenAI/Gemini + TTS orchestrator | React hiện hành |
| `WS /api/v1/voice/stream` | custom PCM16 WebSocket | ZipFormer/Groq + Edge TTS | realtime demo |

Hai luồng không dùng chung transport, ASR selection hoặc cách truyền audio. Ngoài ra,
project đang tự triển khai:

- browser VAD và `MediaRecorder` batching;
- PCM WebSocket protocol, codec/resampling và connection state;
- VAD, endpoint scorer và turn stage;
- STT/TTS orchestration;
- session bridge;
- Agent action/tool-result loop;
- custom event protocol cho transcript, status và binary MP3.

LiveKit đã có abstraction chính thức cho hầu hết những phần trên. Tiếp tục giữ chúng
sau migration sẽ tạo hai runtime cùng làm một việc, làm barge-in, state ownership và
latency khó kiểm soát.

## 3. LiveKit cung cấp những khối nào

### 3.1 `AgentServer`, job và Room

Agent server đăng ký với LiveKit, nhận job và tạo một process/session cho cuộc gọi.
Frontend và Agent tham gia cùng một Room như các realtime participant. Agent worker
có thể deploy trên LiveKit Cloud hoặc hạ tầng container riêng.

Tài liệu: [LiveKit Agents overview](https://docs.livekit.io/agents/) và
[self-hosted agent deployment](https://docs.livekit.io/deploy/custom/deployments/).

### 3.2 `AgentSession` và `RoomIO`

`AgentSession` là orchestrator chính cho input, pipeline và output. `RoomIO` mặc định
quản lý audio track giữa Room và Agent. Session phát event cho user/agent state,
transcript, conversation item và close.

Tài liệu: [AgentSession](https://docs.livekit.io/agents/logic/sessions/).

### 3.3 Turn handling và barge-in

LiveKit cung cấp VAD, endpointing, turn detector, interruption, false-interruption
recovery và preemptive generation. Đây là nơi thay custom browser/server VAD và
logic không cho user nói khi Agent đang `processing`/`speaking`.

Tài liệu: [turn handling](https://docs.livekit.io/agents/logic/turns/) và
[turn-taking tuning](https://docs.livekit.io/agents/logic/turns/tuning/).

### 3.4 Agent, task, workflow và tools

- `Agent` giữ quyền điều khiển dài hạn, instructions và tools;
- `AgentTask[T]` tạm thời điều khiển session để hoàn thành một mục tiêu và trả typed result;
- function tool thực hiện truy vấn hoặc side effect;
- handoff chuyển quyền sang Agent khác khi thật sự có persona/quyền khác nhau;
- `userdata` giữ typed runtime state theo session.

Tài liệu: [workflows](https://docs.livekit.io/agents/logic/workflows/),
[tasks](https://docs.livekit.io/agents/logic/tasks/),
[function tools](https://docs.livekit.io/agents/logic/tools/definition/) và
[passing state](https://docs.livekit.io/agents/logic/agents-handoffs/).

### 3.5 Extension points chính thức

LiveKit cho phép override `stt_node`, `llm_node`, `tts_node`, `transcription_node`,
`on_enter`, `on_exit` và `on_user_turn_completed`. AloSM dùng các hook này cho xử lý
địa danh, confidence/PII gate và cách đọc số tiền; không sửa source LiveKit.

Tài liệu: [pipeline nodes and hooks](https://docs.livekit.io/agents/logic/nodes/).

### 3.6 Observability và testing

SDK cung cấp metrics theo provider, latency theo turn, usage theo session và
`SessionReport` cuối phiên. Test framework hỗ trợ assert message, tool call, handoff
và multi-turn; simulation hiện là beta và text-first nên ASR/audio vẫn cần benchmark
riêng của AloSM.

Tài liệu: [metrics and data hooks](https://docs.livekit.io/deploy/observability/data/)
và [testing/evaluation](https://docs.livekit.io/agents/start/testing/).

## 4. Kiến trúc đích framework-native

```text
┌───────────────────────────────────────────────────────────────┐
│ React                                                         │
│ LiveKit Session + mic/audio tracks + transcript + agent state │
└───────────────────────────────┬───────────────────────────────┘
                                │ WebRTC
┌───────────────────────────────▼───────────────────────────────┐
│ LiveKit Room / SFU                                            │
└───────────────────────────────┬───────────────────────────────┘
                                │
┌───────────────────────────────▼───────────────────────────────┐
│ AloSM AgentServer                                             │
│                                                               │
│ AgentSession[AloSMSessionData]                                │
│ ├── LiveKit RoomIO                                            │
│ ├── LiveKit VAD + endpointing + interruption                  │
│ ├── Vietnamese streaming STT                                  │
│ ├── AloSMAgent                                                │
│ │   ├── BookingTask                                           │
│ │   ├── lookup/FAQ tools                                      │
│ │   └── handoff tool                                          │
│ ├── Vietnamese streaming TTS                                  │
│ └── LiveKit events, metrics và SessionReport                  │
└───────────────────────────────┬───────────────────────────────┘
                                │ function tools
┌───────────────────────────────▼───────────────────────────────┐
│ AloSM application services                                   │
│ PlaceSearch · Quote · Booking · Trip · Handoff · Persistence  │
└───────────────────────────────────────────────────────────────┘
```

FastAPI không còn nằm trên audio data path. Backend giữ vai trò control/business
plane:

- xác thực user và cấp LiveKit token;
- tạo/liên kết AloSM session với room/participant;
- cung cấp hoặc gọi application services;
- lưu durable booking state, transcript cần thiết và audit;
- quản lý operator queue/handoff metadata.

Frontend production dùng token endpoint của FastAPI với auth hiện tại. API key và
secret của LiveKit không được đưa xuống browser. `TokenSource` của LiveKit sẽ lấy
JWT, kết nối Room và dispatch đúng Agent. Xem
[frontend authentication](https://docs.livekit.io/frontends/build/authentication/).

## 5. Cách thiết kế nghiệp vụ đặt xe trong LiveKit

### 5.1 Root Agent

Một `AloSMAgent` giữ hội thoại tổng quát và chỉ expose nhóm capability cần thiết:

- bắt đầu đặt xe;
- tra cứu chuyến;
- FAQ/hỏi cước;
- yêu cầu tổng đài viên;
- kết thúc cuộc gọi.

Không nên tạo nhiều Agent chỉ để biểu diễn từng bước pickup/destination. LiveKit
khuyến nghị handoff khi có persona, model hoặc permission boundary khác nhau. Thu
thập dữ liệu đặt xe phù hợp hơn với `AgentTask`.

### 5.2 Booking Task

`BookingTask` nhận quyền tạm thời, thu thập và sửa:

- pickup;
- destination;
- vehicle type;
- resolved place selection;
- active quote;
- explicit confirmation.

Task trả typed `BookingResult` hoặc kết quả cancelled/handoff. Các hành động bên
ngoài chạy qua function tools.

`TaskGroup` có regression về bước trước rất phù hợp với việc sửa pickup/destination,
nhưng tài liệu hiện đánh dấu **experimental**. Baseline nên dùng `AgentTask` ổn định;
chỉ thử `TaskGroup` sau một spike và phải khóa version SDK nếu chấp nhận dùng beta.

### 5.3 Function tools

Tool nên là wrapper mỏng quanh application service hiện tại:

```text
search_place      → PlaceSearchService
estimate_fare     → QuoteService hoặc fake deterministic provider
create_booking    → BookingService hoặc fake provider
lookup_trip       → TripService
request_handoff   → HandoffService + LiveKit Room/operator flow
```

LiveKit sở hữu tool loop; AloSM service sở hữu validation và side effect. Không giữ
`AgentToolExecutor` loop chạy song song với LiveKit tool loop.

Tool side effect phải giữ các kiểm tra deterministic:

- booking chỉ sau explicit confirmation;
- quote phải khớp pickup, destination và vehicle hiện hành;
- sửa route/vehicle phải vô hiệu quote và confirmation cũ;
- `idempotency_key` bắt buộc;
- timeout không được tự suy diễn là thất bại hay thành công;
- kết quả không xác định phải reconciliation hoặc handoff;
- PII và audit không phụ thuộc prompt.

Đây là business policy, không phải việc tự xây lại framework.

### 5.4 State ownership

Chỉ có ba lớp state với trách nhiệm rõ ràng:

| State | Owner | Mục đích |
|---|---|---|
| Room/media/session lifecycle | LiveKit | participant, track, listening/thinking/speaking, disconnect |
| Runtime booking draft | typed `AgentSession.userdata` | dữ liệu đang thu thập trong cuộc gọi |
| Durable business truth | PostgreSQL/repository | user, quote, booking, handoff, audit và recovery |

Chat context không phải database. `userdata` không được coi là durable booking store.
Mọi side effect quan trọng phải persist qua service/repository.

## 6. Lựa chọn pipeline cho tiếng Việt

### 6.1 Dùng cascaded STT–LLM–TTS trước

Baseline nên dùng pipeline tách rời thay vì speech-to-speech realtime model vì đề
cần đo riêng ASR accuracy, địa danh và latency từng stage. Pipeline tách rời cũng dễ:

- thay/benchmark STT tiếng Việt;
- sửa địa danh trước LLM;
- áp dụng confidence gate;
- kiểm soát câu trả lời trước TTS;
- đo STT, LLM, tool và TTS độc lập.

LiveKit Inference hiện liệt kê các STT có `vi` như Deepgram Nova-3 và cho phép chọn
`auto:vi`; TTS catalog cũng có model hỗ trợ `vi`. Hỗ trợ ngôn ngữ không chứng minh
độ chính xác địa danh, nên provider phải được chọn bằng AloSM benchmark.

Tài liệu: [STT models](https://docs.livekit.io/agents/models/stt/) và
[TTS models](https://docs.livekit.io/agents/models/tts/).

### 6.2 Turn detection tiếng Việt

LiveKit audio/semantic turn detector hiện công bố hỗ trợ 14 ngôn ngữ và **không có
tiếng Việt**. Không nên dùng nó như một tính năng đã được hỗ trợ cho `vi`.

Baseline framework-native:

```text
AgentSession
→ turn_detection="vad"
→ LiveKit VAD + endpointing
→ interruption của LiveKit
```

Sau đó benchmark thêm adaptive interruption. Không tự viết turn detector mới trước
khi VAD/endpointing của framework được đo và chứng minh không đạt yêu cầu.

Tài liệu: [LiveKit turn detector — supported languages](https://docs.livekit.io/agents/logic/turns/turn-detector/).

## 7. Mapping source hiện tại sang kiến trúc mới

### 7.1 Thay bằng LiveKit

| Source hiện tại | Hướng xử lý |
|---|---|
| `src/voice/gateway.py` | thay bằng `AgentSession` và RoomIO |
| `src/voice/audio/codec.py` | bỏ khỏi web-call runtime |
| `src/voice/audio/vad.py` | thay bằng LiveKit VAD/turn handling |
| `src/voice/session_bridge.py` | bỏ sau khi tools/state đã port |
| custom WS `/voice/stream` | thay bằng LiveKit Room/WebRTC |
| REST `/voice/turn` | bỏ sau cutover |
| custom WS event schemas | thay bằng LiveKit event/data APIs |
| browser `MediaRecorder` VAD | thay bằng LiveKit mic track/session |
| manual agent status | lấy từ LiveKit agent/user state |
| `SessionService` tool loop | thay bằng LiveKit Agent/tool loop |
| `AgentToolExecutor` dispatch loop | thay bằng typed LiveKit function tools |

### 7.2 Port vào extension point LiveKit

| Logic có giá trị | Đích mới |
|---|---|
| place aliases/gazetteer | STT/transcription hook hoặc provider keyterms |
| transcript normalization | `on_user_turn_completed` hoặc transcription node |
| confidence policy | STT event/hook + booking confirmation policy |
| spoken formatting/pronunciation | TTS text transform hoặc `tts_node` |
| output/PII review | pre-TTS hook và tool boundary |
| booking typed models | `userdata`, task result và service DTO |
| confirmation/idempotency policy | function tool/service validation |
| conversation/latency metrics | LiveKit events + AloSM evaluation sink |

### 7.3 Giữ làm application/domain layer

- Maps/place provider adapter;
- quote/pricing provider;
- booking/trip service;
- persistence repository và schema;
- auth/user service;
- handoff/operator queue;
- domain validation, PII policy và audit;
- ASR dataset, entity scoring và task-completion evaluation.

## 8. Refactor full nhưng không big-bang

Kiến trúc đích là full LiveKit; cách triển khai vẫn phải theo vertical slice để có
baseline và rollback.

### Pha A — Framework spike

- thêm LiveKit AgentServer/AgentSession và React client;
- dùng provider STT/TTS tiếng Việt;
- chưa nối business thật;
- đo WebRTC, endpointing, barge-in và voice-to-voice latency.

### Pha B — Happy path native

- tạo `AloSMAgent`, `BookingTask`, typed `userdata` và function tools;
- tools gọi fake/deterministic Place, Quote và Booking service;
- hoàn thành pickup → destination → vehicle → quote → confirm → booking;
- không đi qua `SessionService.process_message()` hoặc tool loop cũ.

### Pha C — Safety, persistence và HITL

- durable state/audit;
- low-confidence confirmation fallback;
- typed input fallback qua LiveKit data/text API;
- web operator joins Room hoặc SIP warm transfer tùy demo;
- session report và metrics sink.

### Pha D — Cutover

- frontend chuyển hoàn toàn sang LiveKit;
- chạy benchmark A/B với flow cũ;
- đạt acceptance gate rồi mới xóa `/voice/turn`, `/voice/stream`, `VoiceGateway`,
  browser VAD và tool loop cũ.

Trong Pha A–C có thể giữ runtime cũ làm rollback, nhưng **một cuộc gọi chỉ chạy một
orchestrator**. Không cho LiveKit và `SessionService` đồng thời quyết định tool/state.

### Versioning trong thời gian migration

Các package LiveKit phải khóa theo bộ version đã test trong `uv.lock` và
`package-lock.json`; không dùng range mở rồi để Python/React SDK tự lệch nhau.
`TaskGroup`, Python `WarmTransferTask` và agent simulations hiện được tài liệu đánh
dấu beta/experimental. React `useSession` cũng đang được phát triển tích cực. Nếu
dùng các API này, cần spike, pin version và có test contract trước khi đưa vào
critical path. Dùng API cấp thấp hơn nhưng vẫn thuộc LiveKit Room SDK không bị coi là
tự xây framework.

## 9. Deployment và PII

### 9.1 Deployment

Có thể giữ yêu cầu deploy Fly.io theo mô hình:

```text
React/FastAPI trên Fly.io
AgentServer là process/container riêng trên Fly.io
LiveKit Cloud quản lý Room/media và có thể quản lý Inference
```

Agent worker là tiến trình sống lâu, đăng ký ra ngoài bằng WebSocket và không cần
public inbound port cho job. Cần cấu hình graceful shutdown đủ dài vì cuộc gọi đang
chạy không nên bị cắt khi deploy. Tài liệu LiveKit đưa mức khởi đầu tham khảo 4 CPU,
8 GB cho một agent server phổ biến; cấu hình thật phải dựa trên load test, đặc biệt
nếu chạy model/VAD local.

Không nên nhét AgentServer vào cùng lifecycle của FastAPI web process chỉ để giảm
số service. Hai loại process có scaling, draining và failure mode khác nhau.

### 9.2 Audio, transcript và PII

LiveKit Inference là zero-data-retention cho dữ liệu gửi tới model provider, nhưng
điều đó tách biệt với Agent Observability. Khi observability được bật, audio,
transcript, traces và logs có thể được upload; mặc định `AgentSession.start()` có
thể record đầy đủ và Cloud áp dụng retention window theo plan/config.

AloSM phải cấu hình `record` theo consent và data-minimization policy, không dựa vào
chữ “ZDR” để kết luận rằng không có dữ liệu nào được lưu. Với demo chứa PII, baseline
nên tắt audio recording nếu chưa có consent rõ ràng, chỉ bật metrics/traces đã loại
PII khi cần. Xem [Agent insights và recording options](https://docs.livekit.io/deploy/observability/insights/)
và [LiveKit Inference ZDR](https://docs.livekit.io/agents/models/inference/).

## 10. Acceptance gate bắt buộc

Migration chỉ được coi là tốt hơn khi đạt:

- một web call duy nhất qua WebRTC, không upload cả utterance;
- barge-in dừng audio Agent và tiếp nhận lượt mới ổn định;
- session không lẫn state giữa nhiều cuộc gọi;
- pickup/destination/vehicle có thể sửa trước xác nhận;
- booking không xảy ra nếu thiếu explicit confirmation;
- retry/reconnect không tạo booking lặp;
- transcript, tool call, handoff và latency có trace;
- ASR WER/CER và entity accuracy không thấp hơn baseline;
- task completion rate không thấp hơn baseline;
- p50/p95 endpointing, STT, LLM, tool, TTS TTFB và voice-to-voice được báo cáo;
- typed fallback và handoff giữ được context đã thu thập;
- audio/transcript/PII retention được cấu hình và kiểm chứng.

## 11. Những điều không nên làm

- không bọc toàn bộ `SessionService` cũ trong `llm_node` rồi gọi đó là kiến trúc cuối;
- không giữ custom WebSocket/VAD bên cạnh RoomIO;
- không để LiveKit và AloSM cùng có tool loop;
- không lưu business truth chỉ trong chat context hoặc `userdata`;
- không đặt confirmation/PII/idempotency chỉ trong prompt;
- không dùng `TaskGroup` beta làm critical path mà không spike và khóa version;
- không dùng semantic turn detector chưa hỗ trợ tiếng Việt như thể đã được đảm bảo;
- không chọn provider chỉ vì catalog ghi `vi`; phải benchmark audio thật;
- không xóa runtime cũ trước khi flow mới đạt acceptance gate.

## 12. Quyết định đề xuất

1. Chọn LiveKit làm framework duy nhất cho Voice Agent runtime.
2. Dùng Python Agents SDK để tái sử dụng service/domain code Python hiện tại.
3. Dùng cascaded streaming STT–LLM–TTS cho baseline.
4. Dùng LiveKit VAD/endpointing cho tiếng Việt trước; benchmark adaptive interruption.
5. Dùng một root Agent và stable `AgentTask` cho booking flow.
6. Dùng LiveKit function tools gọi application services; loại bỏ tool loop cũ sau cutover.
7. Giữ deterministic business policy và PostgreSQL ngoài prompt/chat context.
8. Chỉ thử `TaskGroup`/warm-transfer Python beta sau khi happy path ổn định.
9. Triển khai full target theo vertical slice và acceptance gate, không rewrite big-bang.
