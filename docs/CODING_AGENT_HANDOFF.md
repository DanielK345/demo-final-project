# AloSM LiveKit — coding-agent handoff

Cập nhật: **2026-08-20** · Trạng thái: **Phase 3 implemented, Phase 4 evaluation in progress**.

Đây là điểm vào bắt buộc cho developer hoặc coding agent mới. Mục tiêu của tài liệu
là trả lời bốn câu hỏi trước khi sửa code: hệ thống đang chạy gì, phần nào đã hoàn
thành, phần nào còn thiếu và thay đổi tiếp theo phải nằm ở boundary nào.

## 1. Thứ tự đọc bắt buộc

1. Tài liệu này.
2. [`LIVEKIT_TEAM_SETUP.md`](LIVEKIT_TEAM_SETUP.md) để cài và chạy đúng ba process.
3. [`LIVEKIT_MIGRATION_IMPLEMENTATION.md`](LIVEKIT_MIGRATION_IMPLEMENTATION.md) để hiểu kiến trúc và quyết định đã chốt.
4. [`PHASE4_EVALUATION_PLAN.md`](PHASE4_EVALUATION_PLAN.md) nếu làm reliability, benchmark hoặc cutover.
5. [`PROJECT_SOURCE_OF_TRUTH.md`](PROJECT_SOURCE_OF_TRUTH.md) nếu đụng DB, Maps, pricing, fleet, telephony, policy hoặc production readiness.
6. [`../mustdo.md`](../mustdo.md) chỉ cho việc cần credential, hạ tầng, dữ liệu business hoặc phê duyệt con người.

Khi tài liệu mâu thuẫn, ưu tiên code runtime + migration + test, sau đó tài liệu
handoff này, implementation spec, subsystem contract và cuối cùng mới đến PRD/history.

## 2. Mục tiêu và ranh giới đã chốt

AloSM refactor toàn bộ **Voice Agent runtime** sang LiveKit Agents. Không tự dựng
transport, audio pipeline, VAD, turn loop hoặc WebSocket voice song song.

LiveKit sở hữu:

- Room/WebRTC, audio tracks và realtime data;
- agent dispatch/lifecycle;
- `AgentSession`, STT → LLM/tools → TTS orchestration;
- VAD, endpointing, interruption/barge-in;
- transcript/chat context, events và metrics.

AloSM chỉ bổ sung nghiệp vụ tại extension point chính thức:

- một `AloSMAgent`;
- một stable `BookingTask` và native `@function_tool`;
- typed `AgentSession.userdata`;
- place, quote, booking và handoff application services;
- persistence, explicit confirmation, idempotency và PII policy;
- structured booking state qua LiveKit data channel.

Không thêm agent thứ hai, custom audio component, custom VAD, custom orchestration
loop hoặc REST utterance vào happy path nếu chưa có benchmark chứng minh API native
không đáp ứng yêu cầu.

## 3. Runtime hiện tại

```text
Authenticated React user
  → FastAPI POST /api/v1/livekit/token
  → LiveKit Cloud Room/WebRTC
  → local alosm-voice AgentServer worker
  → AgentSession
     ├─ Silero VAD + fixed endpointing
     ├─ Google Chirp 2 STT (official LiveKit Google plugin)
     ├─ OpenAI GPT-4.1 mini LLM (official LiveKit OpenAI plugin)
     ├─ AloSMAgent / BookingTask / native function tools
     └─ Cartesia Sonic 3 TTS through LiveKit Inference
  → LiveKit audio + transcript + alosm.booking_state.v1
  → React UI
```

FastAPI là control/business plane, không nằm trên audio data path. Worker là process
riêng và hiện chạy local; chưa deploy agent lên LiveKit Cloud.

### Model baseline đang được team test

| Stage | Provider path | Model/config |
|---|---|---|
| VAD | LiveKit Agents | Silero, `turn_detection=vad` |
| STT | Google plugin | `chirp_2`, `vi-VN`, region từ ENV |
| LLM | OpenAI plugin | `gpt-4.1-mini` |
| TTS | LiveKit Inference | `cartesia/sonic-3`, language `vi`, pinned voice ID trong `.env.example` |
| Interruption | LiveKit Agents | VAD baseline, không dùng Adaptive quota |

Đây là pipeline hybrid hợp lệ của LiveKit, không phải bốn component tự viết. STT
và LLM dùng billing/quota Google/OpenAI riêng; TTS dùng LiveKit Inference credits.

## 4. Source map

| Boundary | Source chính |
|---|---|
| Worker/session construction | `src/voice_agent/server.py` |
| Provider/model config | `src/voice_agent/config.py` |
| Call-level agent | `src/voice_agent/agent.py` |
| Booking activity/tools | `src/voice_agent/tasks/booking.py` |
| Typed runtime state | `src/voice_agent/session_data.py` |
| Durable state | `src/voice_agent/persistence.py` |
| UI state publish | `src/voice_agent/state_sync.py` |
| JSONL/events/metrics | `src/voice_agent/observability.py` |
| Spoken currency normalization | `src/voice_agent/tts_text.py` |
| LiveKit token endpoint | `src/backend/api/routes/livekit.py` |
| Auth/session access | `src/backend/api/routes/sessions.py` |
| Token/room construction | `src/backend/services/livekit_service.py`, `src/voice_agent/tokens.py` |
| React LiveKit session | `src/frontend/src/features/livekit/LiveKitVoiceSession.tsx` |
| React session ownership | `src/frontend/src/features/ai-assistant/context/VoiceAssistantContext.tsx` |
| Place resolver | `src/backend/services/place_search_service.py` |
| DB migration | `alembic/versions/0005_livekit_voice_state.py` |

## 5. Đã implement

### Realtime và session

- React dùng LiveKit `TokenSource`, `useSession`, `SessionProvider`, microphone,
  `RoomAudioRenderer`, transcript và text message APIs.
- Token endpoint giữ room/identity/metadata ở server; client không tự chọn security boundary.
- Room dispatch đúng agent name `alosm-voice`.
- Session mới, kết thúc, reconnect và recovery đã nối với auth/backend hiện có.
- Access token chỉ trả `401` khi auth thật sự sai. Session cache cũ trả `409`, không
  làm mất đăng nhập; frontend kiểm tra `/auth/me` trước khi dùng hoặc end session.
- Tạo session có in-flight Promise lock để double click/remount không tạo hai session.
- Auto-retry LiveKit chỉ chạy khi có failure reason thật, không retry cleanup tạm của React StrictMode.

### Conversation và booking

- Typed pickup, destination, vehicle, quote, confirmation, booking, failure và handoff state.
- Tìm/chọn candidate địa điểm; alias + fuzzy matching bảo thủ, không biến free text thành place ID.
- Sửa pickup/destination/vehicle làm mất hiệu lực quote, confirmation và booking result phụ thuộc.
- Explicit confirmation trước `create_booking`.
- Booking ID deterministic/idempotent cho cùng session + quote; retry/reconnect không được tạo mã thứ hai.
- State publish về frontend bằng topic `alosm.booking_state.v1`.
- Tiền được chuẩn hóa thành lời tiếng Việt trước TTS; không đọc chuỗi số rời rạc.

### Persistence, fallback và handoff

- `voice_agent_state` + optimistic revision được lưu trong `ride_sessions`.
- Worker restore draft trước khi bắt đầu AgentSession.
- Low-confidence location yêu cầu nói lại hoặc nhập tay.
- STT/LLM/TTS/provider failures được map thành typed failure và recovery action.
- Handoff tool tạo record/context redacted và publish handoff ID.
- JSONL local có state, transcript opt-in, timing, tool lifecycle, usage và lỗi;
  không ghi token, credential, raw audio, tool payload hoặc PII không cần thiết.

## 6. Đã test đến mức nào

Đã có automated unit/API tests cho config, token route, booking task/state,
correction invalidation, persistence, recovery, handoff, observability, session
ownership và TTS text normalization. Frontend lint/build và nhiều Cloud/browser
smoke đã pass trong quá trình Phase 1–3.

Owner đã test thủ công browser trong môi trường yên tĩnh:

- nghe/nói realtime;
- happy path booking;
- thay đổi điểm đón, điểm đến và loại xe;
- phục hồi state;
- Google STT + OpenAI LLM + Sonic 3 TTS có latency chấp nhận được.

Điều này là **baseline evidence**, chưa phải benchmark/release gate.

## 7. Chưa hoàn tất

| Hạng mục | Trạng thái thật | Phase/owner |
|---|---|---|
| ASR WER/CER theo accent/noise | Chưa có corpus + report | Phase 4 Voice |
| Entity accuracy địa danh | Chưa có evaluation dataset đủ lớn | Phase 4 Voice |
| First-turn/missed-turn/false interruption | Có JSONL, chưa aggregate | Phase 4 Voice |
| Latency stage p50/p95 | Có raw metrics, chưa có report | Phase 4 Voice |
| Task completion/correction rate | Có test case, chưa có evaluation suite định lượng | Phase 4 Voice |
| Model A/B accuracy/latency/cost | Chưa chạy cùng một dataset | Phase 4 Voice |
| Browser/device/network matrix | Test thủ công hạn chế | Phase 4 Voice |
| Operator thật join/takeover | Mới có handoff request/context | External + Phase 4 E2E |
| Maps/geocoder/route production | Gazetteer/demo service | Backend/Product external |
| Fleet/dispatch/booking provider thật | Chưa nối | Backend/Ops external |
| Telephony/SIP | Chưa có provider/số/queue | Platform external |
| Production privacy/retention/SLA | Chưa sign-off | Owner/Legal/DevOps |

Known reliability issue cần đưa vào dataset: trong môi trường ồn hoặc một số lượt
đầu, UI có thể ở trạng thái listening nhưng STT chưa tạo final transcript; người dùng
phải nói lại. Không tune VAD tiếp bằng cảm giác — phải tái hiện và đo trong Phase 4.

## 8. Việc tiếp theo

Thực hiện [`PHASE4_EVALUATION_PLAN.md`](PHASE4_EVALUATION_PLAN.md) theo thứ tự:

1. khóa baseline model/config;
2. tạo corpus và expected result;
3. benchmark ASR/entity;
4. benchmark turn-taking/barge-in;
5. behavioral task evaluation;
6. browser/device/network E2E;
7. latency/cost p50/p95;
8. model A/B trên cùng dataset;
9. fallback/reconnect/handoff drill;
10. cutover sau khi gate đạt.

Không xóa legacy trước Phase 4 gate. Phase 5 mới xóa `/voice/turn`, `/voice/stream`,
browser VAD/recorder và tool loop cũ nếu không còn production caller.

## 9. Chạy local

```bash
cd /home/yennguyen/P-160
uv sync
uv run alembic upgrade head

cd src/frontend
npm ci
```

Ba terminal, mỗi lệnh chỉ chạy một lần:

```bash
# Terminal 1
cd /home/yennguyen/P-160
APP_ENV=development make livekit-backend

# Terminal 2
cd /home/yennguyen/P-160
APP_ENV=development \
LIVEKIT_DEBUG_EVENT_LOG=true \
LIVEKIT_DEBUG_TRANSCRIPTS=true \
make livekit-worker

# Terminal 3
cd /home/yennguyen/P-160
make livekit-frontend
```

Mở `http://localhost:5173`. Chi tiết credential, Google ADC, troubleshooting và
test flow nằm trong [`LIVEKIT_TEAM_SETUP.md`](LIVEKIT_TEAM_SETUP.md).

## 10. Verification trước khi handoff

Chạy tối thiểu theo phạm vi thay đổi:

```bash
UV_CACHE_DIR=/tmp/alosm-uv-cache uv run pytest \
  tests/test_voice_agent \
  tests/test_api/test_livekit_routes.py \
  tests/test_api/test_routes.py -q

cd src/frontend
npm run lint
npm run build
```

Không coi một readiness failure do database test chưa được migrate là voice
regression; nhưng phải ghi rõ failure, không tự bỏ test khỏi release report.

## 11. Quy tắc cho coding agent

- Không đọc hoặc in secret từ `.env`; chỉ kiểm tra tên/provider/model không nhạy cảm.
- Không sửa `.env` thật khi task chỉ yêu cầu docs hoặc analysis.
- Không khởi tạo Core Agent legacy trong LiveKit worker.
- Không thêm provider adapter custom trước benchmark.
- Không đưa toàn bộ nghiệp vụ vào prompt; guardrail quan trọng phải nằm trong typed state/tool/service.
- Không để LLM tạo place ID, fare, ETA hoặc booking ID.
- Không nói booking thành công khi chưa có persisted result.
- Không persist raw transcript/audio mặc định.
- Không đánh dấu production-ready khi Maps/Fleet/Telephony/Legal còn external-blocked.
- Tôn trọng dirty worktree; thay đổi hiện hữu không mặc nhiên thuộc task mới.

## 12. Cách giao task cho coding agent tiếp theo

Không cần paste toàn bộ lịch sử chat. Cho agent chạy trong repository này và gửi
prompt tối thiểu theo mẫu:

```text
Đọc đầy đủ docs/CODING_AGENT_HANDOFF.md trước khi hành động, rồi đọc các tài liệu
được nó routing theo đúng phạm vi task. Đối chiếu tài liệu với code/test hiện tại;
không coi docs lịch sử hoặc docs/voice-ai legacy là runtime đang chạy.

Task: <một mục tiêu cụ thể>
Observed failure/evidence: <call ID, JSONL path, error hoặc test case; không paste secret>
Expected behavior: <kết quả mong muốn>
Allowed scope: <file/subsystem được phép sửa>
Required verification: <test, frontend build hoặc evaluation run>

Giữ LiveKit framework làm owner của realtime/audio/VAD/turn orchestration. Nghiệp
vụ AloSM chỉ đi qua Agent/Task/function tools/typed userdata/application services.
Không sửa .env thật, không xóa legacy trước Phase 4 gate và không tuyên bố production
ready khi Maps/Fleet/Telephony/operator thật còn external-blocked.
```

Với task reliability/model benchmark, thêm dataset version, baseline config, run ID
và output path theo [`PHASE4_EVALUATION_PLAN.md`](PHASE4_EVALUATION_PLAN.md). Với
task setup, chỉ chia sẻ tên biến ENV hoặc secret qua secret manager; không gửi API
secret/service-account JSON trong issue, chat hoặc Git.
