# AloSM — LiveKit migration implementation handoff

Cập nhật: **2026-08-19** · Trạng thái: **PHASE 3 HARDENING + LIVEKIT TRANSCRIPT REWRITE IMPLEMENTED / E2E RECHECK REQUIRED**

> Đây là tài liệu phải đọc đầu tiên trước khi code migration LiveKit. Nó chốt kiến
> trúc đích và cách triển khai. Code hiện tại vẫn là runtime truth cho tới khi từng
> phase được implement và test; không được mô tả target này là đã chạy.

## 1. Quyết định đã chốt

1. LiveKit là framework duy nhất cho Voice Agent runtime mới.
2. Dùng **một `AloSMAgent`**, không dùng multi-agent cho scope hiện tại.
3. Luồng booking dùng stable `AgentTask`; không đặt `TaskGroup` experimental vào
   critical path của baseline.
4. Dùng cascaded streaming **STT → LLM/tools → TTS**, không dùng speech-to-speech
   realtime model cho baseline.
5. Dùng LiveKit Room/WebRTC, `AgentServer`, `AgentSession`, `RoomIO`, VAD,
   endpointing, interruption, chat context, function tools, events và metrics.
6. Dùng LiveKit `TurnHandlingOptions` với `turn_detection="vad"` cho baseline tiếng Việt vì LiveKit turn detector
   hiện chưa công bố hỗ trợ `vi`.
7. Dùng LiveKit function-tool loop. Flow mới không gọi `LLMAgent.handle()`,
   `SessionService.process_message()` hoặc `AgentToolExecutor.execute()`.
8. Reuse application services/repositories hiện tại ở phía sau function tools;
   không viết lại Maps/Quote/Booking persistence trong Voice Agent.
9. Runtime draft nằm trong typed `AgentSession.userdata`; PostgreSQL là durable
   business truth. Chat context không phải database.
10. FastAPI là control/business plane, không nằm trên audio data path.
11. React dùng LiveKit client/media/data APIs; bỏ browser VAD/utterance upload sau
    cutover.
12. Kiến trúc đích là full LiveKit-native nhưng rollout theo vertical slice, không
    xóa runtime cũ trước acceptance gate.

## 2. Target flow duy nhất

```text
Authenticated React user
→ POST FastAPI LiveKit token endpoint
→ connect LiveKit Room and dispatch alosm-voice Agent
→ publish microphone audio over WebRTC
→ AgentServer receives job
→ AgentSession receives audio through RoomIO
→ Vietnamese streaming STT publishes partial/provider-final fragments
→ LiveKit VAD waits for 2 seconds of silence and closes one logical user turn
→ finalized user turn enters `on_user_turn_completed`
→ privacy-safe transcript rewrite modifies the final `ChatMessage` only when accepted
→ LiveKit-managed transcript/chat context
→ AloSMAgent or active BookingTask
→ LiveKit function tool
→ AloSM application service/repository
→ tool result returned to LiveKit tool loop
→ LLM produces concise Vietnamese response
→ Vietnamese streaming TTS
→ RoomIO publishes audio
→ React plays audio and renders LiveKit transcript/state
```

Không được thêm REST upload hoặc custom WebSocket vào flow mới.

## 3. Ownership

| Concern                                           | Owner sau migration                   | Ghi chú                                               |
| ------------------------------------------------- | ------------------------------------- | ------------------------------------------------------ |
| WebRTC, audio tracks, reconnect                   | LiveKit Room/client SDK               | Không tự gửi PCM/MP3                                |
| Agent job/lifecycle                               | LiveKit`AgentServer`                | Worker riêng FastAPI                                  |
| Pipeline/session                                  | LiveKit`AgentSession`               | Một session cho một cuộc gọi                       |
| VAD/endpointing/barge-in                          | LiveKit turn handling                 | Baseline`vad` cho tiếng Việt                       |
| STT/LLM/TTS orchestration                         | LiveKit                               | Model cấu hình qua ENV                               |
| Final transcript rewrite trước conversation LLM | AloSM`on_user_turn_completed` hook  | Không thay streaming STT hoặc override provider node |
| Conversation/tool loop                            | LiveKit Agent/tools                   | Không giữ loop cũ                                   |
| Runtime booking draft                             | typed`userdata`                     | Không coi là durable                                 |
| Booking workflow                                  | `BookingTask`                       | Typed result, correction được hỗ trợ              |
| Domain validation                                 | AloSM policy/service                  | Deterministic, không chỉ prompt                      |
| External side effects                             | AloSM services                        | Place, quote, booking, trip, handoff                   |
| Durable truth/audit                               | PostgreSQL/repositories               | Idempotency và reconciliation                         |
| UI state                                          | LiveKit state + structured AloSM data | Không parse câu nói để suy state                  |
| Metrics/session report                            | LiveKit + AloSM metric sink           | Đo thêm ASR entity accuracy                          |

## 4. Cấu trúc source đích

Tạo package mới trong thời gian migration để boundary rõ ràng:

```text
src/voice_agent/
├── __init__.py
├── server.py                 # AgentServer, rtc_session entrypoint, CLI
├── config.py                 # LiveKit/model/recording config
├── session_data.py           # AloSMSessionData + BookingDraft typed models
├── agent.py                  # AloSMAgent duy nhất
├── transcript_rewrite.py     # final user-turn rewrite hook + minimal business context
├── tasks/
│   ├── __init__.py
│   └── booking.py            # BookingTask + typed BookingOutcome
├── tools/
│   ├── __init__.py
│   ├── places.py
│   ├── quotes.py
│   ├── bookings.py
│   ├── trips.py
│   └── handoff.py
└── observability.py          # events, metrics, SessionReport persistence
```

Baseline không override các node STT/LLM/TTS và không bọc lại orchestration của
LiveKit. Một lifecycle hook `on_user_turn_completed` được dùng có chủ đích để rewrite
final transcript trước LLM; partial streaming transcript, endpointing và STT provider
vẫn do LiveKit sở hữu. Guardrail nghiệp vụ đặt trong prompt, `AgentTask`, function
tool và application service đúng extension point của framework. Chỉ cân nhắc custom
provider/node khác sau khi benchmark chứng minh API native không đáp ứng được.

FastAPI bổ sung control-plane code, không import worker để chạy chung process:

```text
src/backend/api/routes/livekit.py       # authenticated token endpoint
src/backend/services/livekit_service.py # room/identity/metadata/token mapping
```

Frontend bổ sung một LiveKit feature boundary:

```text
src/frontend/src/features/livekit/
├── tokenSource.ts
├── LiveKitVoiceSession.tsx
├── useAloSMVoiceSession.ts
└── contracts.ts
```

Tên file có thể điều chỉnh theo convention thực tế, nhưng ownership và dependency
direction không được thay đổi.

## 5. Dependency direction bắt buộc

```text
LiveKit Agent/Task/Tool
        ↓
application service interface
        ↓
provider/repository
```

Được reuse:

- `PlaceSearchService`;
- `QuoteService`/`PricingService` ở mức fake hoặc deterministic demo;
- `BookingService`;
- `TripService`;
- `HandoffService`;
- persistence repositories và DB models;
- place alias/gazetteer data nếu benchmark chứng minh có ích;
- deterministic confirmation/idempotency/output safety rules.

Không được gọi từ runtime mới:

- `src.voice.gateway.VoiceGateway`;
- `src.voice.session_bridge.SessionBridge`;
- `SessionService.process_message()`;
- `LLMAgent.handle()`;
- `ModelDrivenAgent.handle()`;
- `AgentToolExecutor.execute()`;
- REST `/api/v1/voice/turn`;
- WS `/api/v1/voice/stream`.

Không xóa các module này ngay khi tạo spike. Chỉ xóa/deprecate sau khi mọi caller và
test cần thiết đã được migrate.

## 6. Runtime state contract

`AgentSession.userdata` phải là typed object, tối thiểu chứa:

```text
AloSMSessionData
├── app_session_id
├── call_id
├── user_id
├── participant_identity
├── consent/recording flags
├── booking_draft
│   ├── pickup_query / pickup / pickup_candidates
│   ├── destination_query / destination / destination_candidates
│   ├── vehicle_type
│   ├── quote_id / quote snapshot
│   ├── confirmation status
│   └── booking_id
├── last_asr_confidence/provider metadata nếu provider có
└── handoff state
```

Quy tắc:

- sửa pickup, destination hoặc vehicle phải clear quote và confirmation cũ;
- candidate chưa được chọn không phải resolved place;
- runtime state có thể phục hồi từ durable state, không làm chiều ngược lại;
- không lưu API key, raw auth token hoặc PII không cần thiết trong chat context;
- mọi event durable dùng `app_session_id`, `call_id`, room name và participant ID để
  correlate.

## 7. Agent và BookingTask

### `AloSMAgent`

Agent duy nhất giữ quyền điều khiển cuộc gọi và chỉ expose capability:

- bắt đầu đặt xe;
- tra cứu chuyến;
- FAQ/hỏi cước;
- yêu cầu người thật;
- kết thúc cuộc gọi.

Không tạo `PickupAgent`, `DestinationAgent`, `PricingAgent` hoặc `BookingAgent` riêng.
Đó là các bước/task/tool cùng persona, không phải multi-agent boundary.

### `BookingTask[BookingOutcome]`

Task thu thập:

```text
pickup → resolved pickup
destination → resolved destination
vehicle type
quote
explicit confirmation
booking result
```

Task phải hỗ trợ người dùng sửa field trước khi booking. Task chỉ complete khi:

- booking thành công;
- user hủy flow;
- flow chuyển handoff;
- lỗi không thể phục hồi đã được nói rõ.

Không dùng prompt như state machine duy nhất. Function tool và service validation
phải enforce state transition quan trọng.

## 8. Function-tool contract

Baseline tool set:

| Tool                 | Loại   | Side effect | Policy chính                                                      |
| -------------------- | ------- | ----------- | ------------------------------------------------------------------ |
| `search_place`     | read    | không      | trả typed candidates, không echo free text thành resolved place |
| `select_place`     | state   | không      | candidate ID phải thuộc result hiện hành                       |
| `set_vehicle_type` | state   | không      | enum hợp lệ; clear quote/confirmation khi đổi                  |
| `estimate_fare`    | read    | không      | cần hai resolved places + vehicle                                 |
| `confirm_booking`  | state   | không      | chỉ hợp lệ ở bước awaiting confirmation                      |
| `create_booking`   | write   | có         | confirmation + quote fingerprint + idempotency                     |
| `lookup_trip`      | read    | không      | authorization/ownership check                                      |
| `request_handoff`  | write   | có         | reason code + redacted context                                     |
| `end_call`         | session | có         | graceful close                                                     |

`create_booking` và các write tool phải:

- có timeout;
- dùng idempotency key ổn định cho cùng intent;
- không bị cancel giữa side effect không rollback được;
- không retry mù sau timeout/unknown outcome;
- reconciliation hoặc handoff khi không xác định kết quả;
- log redacted audit record;
- chỉ nói “thành công” sau provider/service result xác thực.

Tool trả dữ liệu ngắn, typed và phục vụ reasoning; không trả nguyên payload provider.

## 9. Models và turn handling

Baseline cấu hình bằng ENV, không hard-code provider vào Agent:

```text
LIVEKIT_URL
LIVEKIT_API_KEY
LIVEKIT_API_SECRET
LIVEKIT_AGENT_NAME=alosm-voice
LIVEKIT_STT_MODEL
LIVEKIT_STT_LANGUAGE=vi
LIVEKIT_LLM_MODEL
LIVEKIT_TTS_MODEL
LIVEKIT_TTS_VOICE
LIVEKIT_TTS_LANGUAGE=vi
LIVEKIT_TURN_DETECTION=vad
LIVEKIT_INTERRUPTION_MODE=vad
LIVEKIT_ENDPOINTING_MODE=fixed
LIVEKIT_ENDPOINTING_MIN_DELAY_SECONDS=2.0
LIVEKIT_ENDPOINTING_MAX_DELAY_SECONDS=3.0
LIVEKIT_INTERRUPTION_MIN_DURATION_SECONDS=0.5
LIVEKIT_INTERRUPTION_MIN_WORDS=1
LIVEKIT_RECORD_AUDIO=false
LIVEKIT_RECORD_TRANSCRIPT
LIVEKIT_RECORD_TRACES
LIVEKIT_RECORD_LOGS
LIVEKIT_DEBUG_EVENT_LOG=false
LIVEKIT_DEBUG_TRANSCRIPTS=false
LIVEKIT_DEBUG_LOG_DIR=logs/livekit
VOICE_TRANSCRIPT_REWRITE_ENABLED=true
VOICE_TRANSCRIPT_REWRITE_MODEL=gpt-4o-mini
VOICE_TRANSCRIPT_REWRITE_BASE_URL=https://api.openai.com/v1
VOICE_TRANSCRIPT_REWRITE_TIMEOUT_SECONDS=3
VOICE_TRANSCRIPT_REWRITE_MINIMUM_CONFIDENCE=0.85
```

Quy tắc provider:

- ưu tiên LiveKit Inference/plugin có sẵn;
- không viết custom STT/TTS adapter trong baseline;
- chỉ dùng ZipFormer/custom provider nếu benchmark chứng minh rõ lợi ích;
- production/dev thiếu credential/model/voice phải fail rõ ràng, không sinh fake
  transcript hoặc audio;
- fake model chỉ được inject trong test;
- pin bộ version Python/JS SDK đã test trong lockfiles.

Transcript rewrite:

- chỉ chạy với final `ChatMessage` trong `on_user_turn_completed`, không gọi trên
  partial STT events;
- cùng một rewriter instance được truyền từ `AloSMAgent` sang active `BookingTask`;
- audio có `transcript_confidence < 0.45` không rewrite và tiếp tục đi qua guard yêu
  cầu khách nói lại;
- provider timeout/error phải fail-open về raw transcript, không làm mất user turn;
- chỉ gửi current transcript cùng booking step/candidate context tối thiểu; không gửi
  raw audio, credential hoặc durable PII không cần thiết;
- pickup/destination đã chọn được gửi dưới dạng canonical `known_booking_places`,
  đúng cùng state đang hiển thị trong khung xác nhận, để sửa các biến thể như
  `Bin Unite`/`biên Uni` thành `VinUni` khi có bằng chứng ngữ âm;
- rewrite được chấp nhận sửa trực tiếp `new_message.content` trước conversation LLM;
  frontend giữ transcript STT màu xám, gộp fragment trong cửa sổ 2 giây và chỉ đổi
  bubble sang màu xanh bằng `normalized_text` sau khi nhận rewrite event;
- latency của hook nằm trong `ChatMessage.metrics.on_user_turn_completed_delay`.

Turn handling baseline (LiveKit Agents 1.6.x API):

```text
turn_handling.turn_detection="vad"
turn_handling.endpointing={mode: "fixed", min_delay: 2.0, max_delay: 3.0}
turn_handling.interruption={enabled: true, mode: "vad"}
turn_handling.preemptive_generation={enabled: false, preemptive_tts: false}
endpointing tune bằng p50/p95, không tune theo cảm giác
```

Preemptive LLM generation phải tắt vì rewrite cần quyền sửa final `ChatMessage`
trước khi conversation LLM chạy. Adaptive interruption và preemptive TTS chỉ bật
sau A/B benchmark. LiveKit semantic turn detector không được coi là supported cho
tiếng Việt ở thời điểm tài liệu này.

## 10. Frontend và auth

### Token endpoint

FastAPI cung cấp endpoint theo LiveKit `TokenSource.endpoint` contract:

```text
POST /api/v1/livekit/token
Authorization: Bearer <AloSM access token>
```

Server phải:

- xác thực AloSM user;
- tự tạo/validate room name và participant identity;
- cố định agent dispatch name `alosm-voice` từ server config;
- tạo `app_session_id`/`call_id` hoặc liên kết session đã tạo;
- chỉ đưa metadata tối thiểu cần thiết;
- không tin `user_id`, agent name hoặc permission client tự gửi;
- không bao giờ trả LiveKit API secret.

### React flow

React dùng LiveKit SDK cho:

- start/end session;
- publish/mute microphone track;
- render agent audio;
- listening/thinking/speaking state;
- realtime transcript;
- typed fallback qua LiveKit text/session message;
- reconnect/disconnect.

Booking progress gửi bằng structured LiveKit data/RPC contract versioned, ví dụ
topic `alosm.booking_state.v1`. Frontend không suy pickup/destination/confirmation
bằng cách parse transcript.

Sau cutover, xóa `useVoiceActivityRecorder` khỏi voice-call flow và không gọi
`/voice/turn`, `/voice/speak` hoặc `/voice/stream` cho hội thoại LiveKit.

## 11. HITL

Baseline web-call handoff:

1. Function tool tạo handoff record và context redacted.
2. Backend đưa request vào operator queue.
3. Operator được cấp token để join đúng LiveKit Room.
4. Khi operator accept, Agent ngừng input/output hoặc rời Room theo policy.
5. Caller và operator tiếp tục trong Room.
6. Accept/decline/end disposition được persist.

Không dùng Python `WarmTransferTask` làm baseline vì nó hiện beta và chủ yếu phục vụ
SIP warm transfer. Có thể spike sau khi web-call happy path hoàn thành.

## 12. Observability, privacy và evaluation

Subscribe và lưu tối thiểu:

- user/agent state transitions;
- final transcript và provider metadata được phép lưu;
- STT latency;
- endpointing delay;
- transcript rewrite applied/reason/confidence/duration và
  `on_user_turn_completed_delay`;
- LLM time-to-first-token;
- tool duration/status;
- TTS time-to-first-byte/audio;
- voice-to-voice p50/p95;
- interruption detection/cancellation latency;
- session usage/cost;
- final `SessionReport` hoặc redacted projection của nó.

LiveKit Inference ZDR không đồng nghĩa Agent Observability không lưu dữ liệu. Cấu
hình recording theo consent; audio mặc định tắt cho đến khi privacy policy cho phép.
Không log raw PII trong tool args, transcript debug hoặc provider payload.

AloSM vẫn phải tự đo:

- WER/CER tiếng Việt;
- entity accuracy cho pickup/destination;
- task completion rate;
- correction success rate;
- booking-without-confirmation rate, mục tiêu bằng 0;
- đúng/sai của fallback và handoff.

## 13. Phases coding

### Phase 0 — Baseline và dependency

- lưu metrics flow cũ để so sánh;
- pin `livekit-agents==1.6.6`, `livekit-client==2.21.0` và
  `@livekit/components-react==2.9.23` trong lockfiles;
- thêm ENV validation;
- thêm package `src/voice_agent` và test skeleton;
- không tạo custom pipeline hook/provider adapter;
- chưa đổi frontend production path.

Gate: imports, config tests và existing test suite không regress.

#### Phase 0 implementation record — 2026-08-17

- Python pin: `livekit-agents==1.6.6`; `livekit-api==1.2.0` được resolve qua
  dependency chính thức và đã import smoke-test thành công.
- React pins: `livekit-client==2.21.0` và
  `@livekit/components-react==2.9.23`; npm dependency tree dedupe đúng một bản
  `livekit-client`.
- Thêm `src/voice_agent/config.py` với `VOICE_RUNTIME=legacy` mặc định, validation
  fail-closed khi chọn `livekit`, credential dùng `SecretStr`, recording mặc định
  tắt và baseline turn detection chỉ cho phép `vad`.
- Thêm package boundary `src/voice_agent/`, `tasks/`, `tools/`; chưa tạo worker,
  `AgentSession`, tool nghiệp vụ, custom hook hoặc provider adapter ở phase này.
- Frontend production path và legacy runtime không thay đổi.
- Verification: config tests `5 passed`, Ruff pass, frontend production build pass,
  Python LiveKit/API imports pass.
- Full suite: `536 passed, 5 skipped, 3 failed`. Ba failure `AGENT-002/003/004`
  là baseline Core Agent correction đã được repo ghi nhận trước migration tại
  `eval_cases/README.md`; Phase 0 không sửa hoặc che các failure này.

### Phase 1 — LiveKit transport spike

- FastAPI authenticated token endpoint;
- AgentServer + AgentSession;
- React kết nối Room;
- STT tiếng Việt → câu trả lời đơn giản → TTS tiếng Việt;
- LiveKit VAD, interruption, transcript và state UI.

Gate: web call realtime chạy end-to-end, barge-in có evidence và không dùng REST
utterance/custom WS.

#### Phase 1 implementation record — 2026-08-18

- Thêm authenticated standard `TokenSource.endpoint` tại
  `POST /api/v1/livekit/token`; room, participant identity, metadata, grants và
  agent dispatch đều do server quyết định. Client chỉ được yêu cầu đúng
  `alosm-voice`.
- Token dùng opaque hashed identity/room name, không đưa user ID thô vào identity;
  JWT giới hạn join đúng một Room và TTL mặc định 10 phút.
- Thêm worker riêng `python -m src.voice_agent.server dev` dùng
  `AgentServer.rtc_session`, một `AgentSession`, `RoomIO` mặc định và một
  `AloSMAgent`; không gọi runtime/tool loop cũ.
- Pipeline native dùng LiveKit Inference: Deepgram Nova-3 `vi` → Gemma 4 31B →
  Cartesia Sonic 3 `vi`, LiveKit Silero VAD và `TurnHandlingOptions` stable của
  SDK 1.6.6.
- React dùng `TokenSource.endpoint`, `useSession`, `SessionProvider`, `useAgent`,
  `useSessionMessages` và `RoomAudioRenderer`; mic/audio/transcript/text fallback
  đều đi qua LiveKit. LiveKit chunk được lazy-load khi
  `VITE_VOICE_RUNTIME=livekit`.
- Cloud evidence: worker registered ở LiveKit Cloud, Room dispatch thành công,
  agent joined và smoke client nhận audio frame thật từ greeting TTS. Không có lỗi
  inference gateway trong lần chạy cuối.
- Automated verification hiện tại: Phase 0/1 tests `13 passed`, Python Ruff pass,
  frontend lint/build pass. Full repository suite: `544 passed, 5 skipped` và đúng
  ba baseline failure đã biết `AGENT-002/003/004`; không xuất hiện failure mới.
- Gate chưa đóng: cần browser microphone test một câu tiếng Việt và evidence
  barge-in/ngắt TTS. Giữ cả `VOICE_RUNTIME` và `VITE_VOICE_RUNTIME` là `legacy`
  cho tới khi review này đạt.

Smoke có thể chạy lại bằng hai terminal:

```bash
uv run python -m src.voice_agent.server dev
uv run python -m scripts.livekit_room_smoke
```

### Phase 2 — Native booking happy path

- `AloSMSessionData`;
- một `AloSMAgent`;
- `BookingTask`;
- native function tools gọi fake/deterministic application services;
- structured booking-state update về React;
- explicit confirmation và idempotent booking.

Gate: pickup → destination → vehicle → quote → confirm → booking chạy lặp lại; flow
mới không gọi tool loop cũ.

#### Phase 2 implementation record — 2026-08-18

- Thêm `AloSMSessionData`, `BookingDraft`, typed place/quote/booking models trong
  `src/voice_agent/session_data.py`; `AgentSession.userdata` là nguồn business state
  duy nhất của runtime mới.
- Dependent-field invalidation được enforce bằng code: tìm/chọn lại pickup,
  destination hoặc đổi vehicle sẽ clear quote, confirmation fingerprint và booking
  result cũ.
- `AloSMAgent` expose đúng một native function tool `start_booking`; tool này await
  trực tiếp một `BookingTask[BookingOutcome]` để SDK thực hiện activity handoff. Không tạo agent
  nghiệp vụ thứ hai và không gọi `LLMAgent`/`SessionService`/`AgentToolExecutor` cũ.
- `BookingTask` dùng native `@function_tool` cho `search_place`, `select_place`,
  `set_vehicle_type`, `estimate_fare`, `prepare_booking_confirmation`,
  `confirm_booking`, `create_booking` và `cancel_booking_flow`.
- Reuse `PlaceSearchService` và `PricingService` deterministic hiện có qua application
  boundaries nhỏ. Không kéo legacy orchestration vào worker; package
  `src.backend.services` được đổi sang lazy exports để import một service không còn
  khởi tạo Core Agent/OpenAI ngoài ý muốn.
- `confirm_booking` kiểm tra lượt user gần nhất phải là xác nhận đặt chuyến rõ ràng;
  `create_booking` còn enforce confirmation + quote fingerprint. Demo booking ID
  deterministic theo app session và quote nên retry cùng intent trả cùng kết quả.
- Structured state được publish bằng reliable LiveKit data channel topic
  `alosm.booking_state.v1`; React nhận packet bằng `useDataChannel` và hiển thị pickup,
  destination, vehicle, quote, confirmation và booking ID. Không thêm REST utterance
  hoặc custom WebSocket.
- Runtime baseline dùng LiveKit VAD cho cả turn detection và interruption. Adaptive
  chỉ còn là explicit opt-in qua `LIVEKIT_INTERRUPTION_MODE=adaptive`, không tiêu quota
  Adaptive Cloud trong baseline Phase 2.
- LiveKit UI có recovery native: khi agent không join, lần đầu UI tự end session cũ
  rồi remount `useSession` đúng một lần; lỗi tiếp theo dừng và hiện nút
  `Tạo lại cuộc gọi`. `session.start()` error cũng có retry thủ công. Call ID mới làm
  token endpoint cấp Room và server-side agent dispatch mới. Không retry vô hạn và
  không tự dispatch bằng REST.
- Backend không còn import/khởi tạo Core Agent legacy trong startup path; `/chat` mới
  lazy-load compatibility agent khi endpoint legacy thực sự được gọi.
- Verification: `27 passed` cho Voice Agent/token/API/Hà Nội happy-path targeted tests;
  Python Ruff pass; frontend lint/build pass. Cloud smoke trên worker tạm có agent
  `alosm-voice` xác nhận `LIVEKIT_AGENT_JOINED=PASS`, `LIVEKIT_AGENT_AUDIO=PASS`,
  `LIVEKIT_BOOKING_STATE=PASS`, `LIVEKIT_BOOKING_HAPPY_PATH=PASS` và
  `LIVEKIT_BOOKING_RESULT_AUDIO=PASS`. Flow text realtime qua Room đã chạy đủ
  pickup → destination → vehicle → quote → explicit confirmation → booking bằng
  Gemma và native LiveKit tools; client nhận audio mới sau khi booking hoàn tất và
  Room được LiveKit `close_on_disconnect`/`delete_room_on_close` dọn sau client rời.
- Browser owner review đã xác nhận microphone STT, TTS, state UI, happy path và flow
  correction nhiều lượt chạy được. Pickup, destination và vehicle correction đều có
  automated invalidation test. Phase 2 gate được đóng; rollout mặc định vẫn giữ
  `legacy` cho tới Phase 4 cutover, không đổi sớm feature flag production.

### Phase 3 — Correction, fallback, persistence và HITL

- sửa pickup/destination/vehicle;
- invalidate quote/confirmation;
- typed fallback;
- low-confidence handling;
- persist/recover durable business state;
- web operator handoff giữ context.

Gate: correction và handoff tests pass; reconnect/retry không duplicate booking.

#### Phase 3 implementation record — 2026-08-18

- Giữ nguyên LiveKit ownership: `AgentSession` tiếp tục sở hữu STT → LLM → TTS,
  turn detection, interruption, Room I/O và text fallback. Phase này chỉ thêm business
  state/application boundaries vào `AgentSession.userdata` và native function tools;
  không thêm audio component, custom WebSocket hoặc orchestration loop.
- `AloSMSessionData` có durable schema versioned cho `BookingDraft`, typed failure và
  handoff state. Public data-channel contract vẫn là `alosm.booking_state.v1`, mở rộng
  backward-compatible bằng `failure`, `handoff`, `recovered`; không persist raw audio,
  transcript, raw ASR query hoặc PII.
- Migration `0005_livekit_voice_state` thêm `voice_agent_state` và
  `voice_state_revision` vào `ride_sessions`. State LiveKit tách khỏi legacy
  `agent_state`; revision độc lập dùng một optimistic `UPDATE ... WHERE revision = ?`
  để phát hiện hai Room cùng sửa một application session mà không giữ transaction dài.
  RLS/revoke hiện có của `ride_sessions` tiếp tục bảo vệ hai cột mới.
- Worker restore draft trước `AgentSession.start`, lấy lại owner từ session row đáng
  tin cậy và phát trạng thái `recovered` về React. Session smoke không có DB row dùng
  explicit ephemeral mode; lỗi restore thật trở thành `SESSION_RECOVERY_FAILED` và
  cuộc gọi vẫn tiếp tục an toàn.
- Low-confidence location dùng trực tiếp `llm.ChatMessage.transcript_confidence` của
  LiveKit. Audio dưới threshold yêu cầu nói lại hoặc nhập tay; text input có confidence
  `None` là fallback hợp lệ. Không wrap hoặc thay STT node.
- Native LiveKit `error` event được map sang `STT_UNAVAILABLE`, `LLM_UNAVAILABLE`,
  `TTS_UNAVAILABLE` rồi persist/publish. Place, quote, unknown booking result và state
  conflict cũng có typed recovery action rõ ràng.
- Mọi mutation của booking task persist trước khi publish UI. Correction vẫn
  invalidate quote/confirmation/booking; booking demo giữ ID deterministic theo
  session + quote và completed result được restore, nên reconnect/retry không sinh mã
  booking thứ hai.
- Thêm native `request_handoff` tool, reuse `HandoffService` hiện có. Chỉ summary bằng
  display name/vehicle/quote/failure được chuyển; không có transcript, raw query hay
  full address. React hiển thị failure fallback, restored state và handoff ID.
- Verification local: Voice Agent/API/LiveKit targeted tests pass; Ruff, frontend lint
  và production build pass. Upgrade → downgrade → upgrade riêng của migration `0005`
  pass trên SQLite. Full migration chain SQLite vẫn bị chặn trước `0005` bởi migration
  legacy `9e9b...` dùng `ALTER CONSTRAINT` không được SQLite hỗ trợ; không sửa ngoài
  scope. Trên Supabase dev, schema được đối chiếu đầy đủ tới `0004` nhưng migration
  history còn marker cũ `fc877ccd583a` không tồn tại trong repo; marker đã được repair
  sang `0004` sau khi xác minh schema, rồi `0005` được apply thành công. Remote hiện ở
  `0005_livekit_voice_state (head)`; hai cột đúng kiểu JSONB/BIGINT, check constraint,
  RLS và least-privilege ACL của `ride_sessions` đều được xác minh sau migration.
- Post-migration Cloud smoke trên worker Phase 3 pass toàn bộ
  `LIVEKIT_AGENT_JOINED`, `LIVEKIT_AGENT_AUDIO`, `LIVEKIT_BOOKING_STATE`,
  `LIVEKIT_BOOKING_HAPPY_PATH` và `LIVEKIT_BOOKING_RESULT_AUDIO`. Browser owner review
  cho reconnect/low-confidence/HITL trên authenticated durable session vẫn là bước
  cuối của Phase 3 test; tài khoản demo ghi trong README không còn đăng nhập được trên
  Supabase dev hiện tại nên không tự động reset credential.

#### Phase 3 conversation hardening — 2026-08-18

- Giữ nguyên một `AgentSession`, một `AloSMAgent` và stable `BookingTask`; không thêm
  pipeline hook, custom audio component, custom WebSocket, multi-agent hoặc
  `TaskGroup` experimental.
- Draft phục hồi được tóm tắt tối thiểu vào instructions của call-level agent, còn
  `BookingTask.on_enter` đọc trực tiếp typed `AgentSession.userdata`. Agent vì vậy có
  thể trả lời pickup/destination cũ mà không đưa candidate list hoặc toàn bộ lịch sử
  vào prompt/chat context.
- Parent chat history được chuyển vào task bằng native
  `chat_ctx.copy(exclude_instructions=True)` theo pattern LiveKit; task giữ prompt
  chuyên biệt nhỏ và không mang lặp system instructions của parent.
- Các terminal tool `create_booking`, `request_handoff`, `cancel_booking_flow` chỉ
  gọi `AgentTask.complete(BookingOutcome)` và trả `None`. Parent agent là owner duy
  nhất của câu kết thúc, loại bỏ hai lượt phát thành công liên tiếp.
- Spoken output dùng nhãn tiếng Việt cho vehicle/target/currency; instructions cấm
  dấu gạch chéo, enum và chữ viết tắt. Booking ID vẫn nằm trong typed state/UI nhưng
  không còn mặc định đọc chuỗi kỹ thuật qua TTS.
- `PlaceSearchService` vẫn là business boundary phía sau native `search_place` tool.
  Resolver bổ sung reverse containment và fuzzy match bảo thủ bằng dependency
  `rapidfuzz` đã có sẵn; chỉ trả candidate khi score cao và cách biệt, mọi candidate
  vẫn phải đi qua `select_place`. Không echo free text và không cho LLM tạo place ID.
- LiveKit VAD baseline được tune bằng native endpointing: fixed `2.0–3.0s`, barge-in
  minimum `0.5s`, một từ; greeting cho phép interruption để không drop câu nói sớm.
  Preemptive LLM generation tắt để conversation LLM chỉ nhận final transcript sau
  rewrite. Các giá trị đều cấu hình qua ENV để benchmark, không tạo detector riêng.
- `RoomOptions.audio_input` bật rõ native automatic gain control và pre-connect audio.
  Enhanced Krisp/ai-coustics chưa bật vì plugin cài riêng và có metered cost; không
  thêm dependency/quota ngầm. Cartesia voice tiếp tục pin qua ENV và cần browser A/B
  bằng voice tiếng Việt được owner duyệt trước khi cutover.
- Regression verification: Voice Agent recovery/state/task/config/persistence cùng
  LiveKit API/service và Hà Nội booking-flow tests pass; browser audio E2E vẫn phải
  chạy lại để chốt endpointing và voice bằng tai nghe/micro thật.
- Thêm `src/voice_agent/observability.py`, subscribe trực tiếp public
  `AgentSession` events cho user/agent state, transcript, conversation metrics,
  speech, overlap/false interruption, tool lifecycle, usage, error và close. Không
  dùng session-level `metrics_collected` đã deprecated; latency lấy từ
  `ChatMessage.metrics`.
- Debug event log phát summary ngắn ra terminal và ghi crash-tolerant JSONL riêng
  theo `call_id` trong `logs/livekit/`. Logging mặc định tắt; transcript là opt-in
  thứ hai. Khi transcript tắt chỉ ghi length/confidence/metrics. Tool arguments,
  tool outputs, raw audio, credentials và token không bao giờ được đưa vào JSONL.

Chạy worker local với evidence đủ để debug ASR/turn-taking:

```bash
LIVEKIT_DEBUG_EVENT_LOG=true \
LIVEKIT_DEBUG_TRANSCRIPTS=true \
make livekit-worker
```

Sau cuộc gọi, xem file mới trong `logs/livekit/<call_id>.jsonl`. Chỉ bật transcript
trong local session đã được phép debug; không dùng cấu hình này làm production default.

#### LiveKit final-transcript rewrite — 2026-08-19

- Tích hợp `OpenAITranscriptRewriter` hiện có vào runtime LiveKit tại lifecycle hook
  `on_user_turn_completed`, tức sau khi Deepgram hoàn tất user turn và trước khi
  LiveKit thêm `ChatMessage` vào context của conversation LLM. Không rewrite partial
  transcript và không override `stt_node`, `llm_node` hoặc `transcription_node`.
- Worker tạo đúng một rewriter cho mỗi job, truyền cùng instance vào `AloSMAgent` và
  `BookingTask`, rồi đóng async provider client trong shutdown callback của job.
- Context rewrite được chiếu từ typed `AloSMSessionData`: booking step, candidate hiện
  hành có ASR aliases và câu hỏi assistant gần nhất. Không nối lại legacy
  `VoiceGateway`, `SessionBridge` hoặc Core Agent orchestration.
- Rewrite giữ nguyên `transcript_confidence`; audio dưới `0.45` được bỏ qua để guard
  low-confidence hiện có yêu cầu nói lại. Provider exception/timeout fail-open về câu
  gốc để LiveKit vẫn xử lý lượt nói.
- Khi rewrite được safety contract chấp nhận, hook chỉ thay text content của final user
  message. Raw frontend STT display không bị trì hoãn; LLM/tool loop nhận bản đã sửa.
- Cấu hình local/sample pin `gpt-4o-mini` qua OpenAI Responses API và timeout 3 giây
  cho realtime. `OPENAI_API_KEY` chỉ được dùng khi
  `VOICE_TRANSCRIPT_REWRITE_ENABLED=true`; credential/quota này tách khỏi LiveKit
  Inference.
- Automated coverage kiểm tra parent agent, active booking task, candidate context,
  preservation của confidence, low-confidence skip và provider fail-open.

#### Terminal session logout — 2026-08-20

- `POST /api/v1/sessions/{session_id}/end` kết thúc conversation session và revoke
  ngay bearer token đã bind với session đó. Token cũ nhận `401` trên protected
  endpoint, kể cả khi localStorage chưa kịp được dọn.
- Lượt text hoặc REST voice mà Core Agent trả `END_SESSION` cũng revoke token trước
  khi response được trả về. Frontend phát xong lời chào kết thúc, xóa auth state rồi
  chuyển về `/login` với history replacement.
- Nút gác máy của cả LiveKit và legacy runtime gọi terminal `endSession`; nút đóng
  popup chỉ đóng giao diện và không logout. Nếu mạng lỗi khi gác máy, frontend vẫn
  xóa credential local; token server còn sót sẽ hết hạn theo TTL hiện hành.
- LiveKit theo dõi transition từ connected sang disconnected: reconnect tạm thời
  không logout, nhưng Room/agent đóng hoặc disconnect cuối cùng sẽ chạy terminal
  cleanup. Disconnect có chủ đích để retry không bị coi là kết thúc session.
- “Đặt xe mới” reset agent memory trong session đang hoạt động, không gọi `/end`,
  tránh logout ngoài ý muốn.

### Phase 4 — Evaluation và cutover

- LiveKit behavioral tests + tool mocks;
- ASR audio benchmark;
- browser/device E2E;
- latency/cost A/B với flow cũ;
- chuyển feature flag/default sang LiveKit.

Gate: mọi acceptance criterion mục 14 đạt.

### Phase 5 — Xóa legacy

- xóa/deprecate `/voice/turn`, `/voice/stream`, `/voice/speak` nếu không còn caller;
- xóa browser VAD/recorder cũ;
- xóa VoiceGateway/SessionBridge/custom WS schema;
- xóa Agent/Session tool loop cũ nếu text path cũng đã migrate hoặc không còn dùng;
- cập nhật README, architecture, ENV và tests thành runtime truth mới.

Gate: `rg` không còn production caller vào legacy path; full tests/build pass.

## 14. Final acceptance criteria

- chỉ một production voice flow qua LiveKit Room/WebRTC;
- chỉ một conversation/tool orchestrator là LiveKit;
- một `AloSMAgent`; booking là task/tool, không phải multi-agent;
- không upload utterance hoàn chỉnh trong happy path;
- user có thể barge-in khi Agent đang nói;
- pickup/destination/vehicle được sửa đúng;
- quote/confirmation cũ bị clear khi dữ liệu phụ thuộc thay đổi;
- create booking trước confirmation bằng 0;
- duplicate booking khi retry/reconnect bằng 0;
- typed fallback và HITL giữ được context;
- transcript/state không lẫn giữa concurrent sessions;
- WER/CER/entity accuracy và task completion có report;
- endpointing/STT/LLM/tool/TTS/voice-to-voice có p50/p95;
- privacy/recording config khớp consent;
- frontend build, backend tests và LiveKit agent tests pass;
- legacy runtime chỉ bị xóa sau khi các gate trên đạt.

## 15. Coding-agent checklist trước mỗi thay đổi

1. Đọc tài liệu này và `LIVEKIT_REFACTOR_RESEARCH.md`.
2. Xác định phase đang thực hiện; không nhảy thẳng sang xóa legacy.
3. Không thêm orchestration ngoài extension point LiveKit.
4. Không tạo Agent thứ hai nếu không có persona/model/permission boundary mới được
   phê duyệt trong docs.
5. Không gọi tool loop cũ trong flow LiveKit.
6. Không chuyển domain guardrail thành prompt-only rule.
7. Thêm test cho state/tool/side effect trước khi đổi caller.
8. Cập nhật trạng thái `NOT IMPLEMENTED` chỉ khi code và test tương ứng đã có.
