# AloSM LiveKit baseline — hướng dẫn setup cho team

Cập nhật: **2026-08-18** · Branch baseline: `feature/agentic-ai` · Commit đầu tiên:
`54a764e`

Tài liệu này dành cho thành viên mới cần lấy source, chạy lại đúng baseline LiveKit
đang có và biết chính xác phần nào đã nối thật, phần nào vẫn là demo. Không đưa
credential vào Git, ticket, ảnh chụp màn hình hoặc nhóm chat.

## 1. Baseline hiện tại là gì?

Đây không phải một worker AI đứng riêng. Luồng đang chạy xuyên qua source hiện có:

```text
React Login/Homepage/VoiceCallPanel hiện có
→ POST /api/v1/livekit/token trên FastAPI hiện có
→ LiveKit Room/WebRTC
→ worker alosm-voice dùng AgentServer + AgentSession
→ Silero VAD → STT tiếng Việt → LLM/function tools → TTS
→ PlaceSearchService/PricingService/HandoffService hiện có
→ voice state trong ride_sessions hiện có
→ LiveKit data channel cập nhật booking state về React
```

LiveKit quản lý media realtime, room, session lifecycle, VAD/endpointing,
interruption, transcript, tool loop và audio output. Code AloSM chỉ bổ sung nghiệp
vụ tại các extension point chính thức: `Agent`, `AgentTask`, `function_tool`, typed
`userdata`, application service và repository.

Runtime cũ vẫn còn sau feature flag để rollback. Khi chạy các lệnh trong tài liệu
này, voice UI chọn LiveKit; web chat/REST voice legacy không nằm trong audio path đó.

## 2. Đã nối với Backend và Frontend chưa?

**Đã nối.** Chi tiết:

| Phần | Trạng thái | Source chính |
|---|---|---|
| Login/Auth hiện có | Đã dùng | Frontend gửi bearer token hiện có tới token endpoint |
| FastAPI hiện có | Đã dùng | `src/backend/api/routes/livekit.py` |
| LiveKit token/room/identity | Đã dùng | `src/backend/services/livekit_service.py`, `src/voice_agent/tokens.py` |
| React Homepage/voice popup | Đã dùng | `VoiceCallPanel.tsx` chọn `LiveKitVoiceSession.tsx` bằng feature flag |
| Micro/loa/transcript realtime | Đã dùng | LiveKit React components/client |
| Agent runtime | Đã dùng | `src/voice_agent/server.py`, `agent.py`, `tasks/booking.py` |
| Tìm địa điểm | Đã nối service hiện có | `PlaceSearchService`; hiện chỉ dùng gazetteer local |
| Báo giá | Đã nối service hiện có | `PricingService`; số liệu demo deterministic |
| Tạo booking | Có flow hoàn chỉnh | Kết quả `demo_*`, chưa gọi hệ thống đội xe thật |
| Handoff | Có tạo record/yêu cầu | Chưa có operator console và chuyển audio tới người thật |
| Database state | Đã nối | Draft/kết quả voice nằm trong `ride_sessions.voice_agent_state` + optimistic revision |
| State hiển thị trên UI | Đã nối | LiveKit data channel topic `alosm.booking.state.v1` |
| Debug log | Đã có | JSONL privacy-gated trong `logs/livekit/` |

Vì vậy đây là **vertical slice tích hợp BE–FE–DB**, nhưng chưa phải nền tảng gọi xe
production hoàn chỉnh.

## 3. Điều kiện trước khi setup

Máy phát triển cần:

- Git;
- Python 3.12;
- `uv`;
- Node.js và npm;
- FFmpeg/FFprobe;
- trình duyệt cho phép microphone;
- quyền đọc repository;
- một LiveKit Cloud project và bộ credential dev, hoặc credential của project
  AloSM được owner chuyển qua secret manager;
- database dev đã migrate nếu muốn test persistence thật.

Baseline hiện dùng LiveKit Cloud cho Room và LiveKit Inference. Worker vẫn chạy trên
máy developer; không cần deploy worker lên LiveKit Cloud để test local. Tuy nhiên
máy phải có Internet và Cloud project vẫn áp dụng quota cho Room/Inference/adaptive
interruption.

## 4. Lấy đúng code

Nếu chưa clone:

```bash
git clone https://github.com/AI20K-Build-Phase-Cohort-3/P-160.git
cd P-160
git switch feature/agentic-ai
```

Nếu đã có repository:

```bash
cd /duong-dan-den/P-160
git fetch origin
git switch feature/agentic-ai
git pull --ff-only origin feature/agentic-ai
```

Kiểm tra baseline đã có:

```bash
git log -1 --oneline
```

Commit phải là `54a764e` hoặc một commit mới hơn trên cùng branch.

## 5. Cài dependency

Tại root repository:

```bash
uv sync
cp .env.example .env
```

Cài frontend theo đúng lockfile:

```bash
cd src/frontend
npm ci
cd ../..
```

Các version quan trọng đã pin:

- `livekit-agents==1.6.6`;
- `livekit-client==2.21.0`;
- `@livekit/components-react==2.9.23`.

Không tự nâng từng package LiveKit riêng lẻ trong lúc setup baseline.

## 6. Cấu hình `.env`

Điền tại file `.env` ở root. Không commit file này.

```env
APP_ENV=development

VOICE_RUNTIME=livekit
VITE_VOICE_RUNTIME=livekit

LIVEKIT_URL=wss://alosm-mvgefaui.livekit.cloud
LIVEKIT_API_KEY=<lay-tu-livekit-dashboard-hoac-secret-manager>
LIVEKIT_API_SECRET=<lay-tu-livekit-dashboard-hoac-secret-manager>
LIVEKIT_AGENT_NAME=alosm-voice
LIVEKIT_NUM_IDLE_PROCESSES=1

LIVEKIT_STT_MODEL=deepgram/nova-3
LIVEKIT_STT_LANGUAGE=vi
LIVEKIT_LLM_MODEL=google/gemma-4-31b-it
LIVEKIT_TTS_MODEL=cartesia/sonic-3
LIVEKIT_TTS_VOICE=<voice-id-dev-da-duoc-team-chot>
LIVEKIT_TTS_LANGUAGE=vi

LIVEKIT_TURN_DETECTION=vad
LIVEKIT_INTERRUPTION_MODE=vad
LIVEKIT_ENDPOINTING_MODE=fixed
LIVEKIT_ENDPOINTING_MIN_DELAY_SECONDS=0.8
LIVEKIT_ENDPOINTING_MAX_DELAY_SECONDS=2.5
LIVEKIT_INTERRUPTION_MIN_DURATION_SECONDS=0.5
LIVEKIT_INTERRUPTION_MIN_WORDS=1

LIVEKIT_RECORD_AUDIO=false
LIVEKIT_RECORD_TRANSCRIPT=false
LIVEKIT_RECORD_TRACES=false
LIVEKIT_RECORD_LOGS=false
LIVEKIT_DEBUG_EVENT_LOG=false
LIVEKIT_DEBUG_TRANSCRIPTS=false
```

Lưu ý:

- `LIVEKIT_URL` dùng `wss://`, không dùng URL dashboard `https://`.
- API key/secret chỉ ở backend và worker; tuyệt đối không đặt vào biến `VITE_*`.
- `LIVEKIT_AGENT_NAME` phải giống giữa token endpoint, frontend và worker.
- `LIVEKIT_NUM_IDLE_PROCESSES=1` giữ sẵn một job process trong local `dev` mode;
  đặt `0` nếu máy rất thiếu RAM, tăng chỉ sau khi đo concurrency/memory.
- Baseline dùng `vad`, không dùng `adaptive`, để tránh quota adaptive interruption
  và giữ đúng cấu hình đã test.
- Lệnh `make livekit-frontend` tự truyền `VITE_VOICE_RUNTIME=livekit`; biến root vẫn
  được ghi rõ để tránh chạy nhầm bằng lệnh thủ công.

### Database development đầy đủ

Để Auth, session recovery và handoff bền vững hoạt động, dùng database dev của team:

```env
DATABASE_URL=<runtime-postgresql-url>
DATABASE_URL_MIGRATIONS=<direct-postgresql-url>
QUOTE_SIGNING_KEY=<secret-it-nhat-32-ky-tu>
FIELD_ENCRYPTION_KEY=<secret-khac-it-nhat-32-ky-tu>
```

Kiểm tra version:

```bash
uv run alembic current
uv run alembic heads
```

Cả hai phải chỉ tới `0005_livekit_voice_state`. Chỉ người đang phụ trách migration
mới chạy lệnh sau trên database dùng chung:

```bash
uv run alembic upgrade head
```

Không chạy migration bằng Supabase transaction pooler. Dùng direct/session URL cho
`DATABASE_URL_MIGRATIONS`.

### Chế độ smoke local không persistence

Nếu chưa được cấp database dev, có thể đặt `APP_ENV=test` để kiểm tra login và voice
flow bằng in-memory adapters. Tài khoản là:

```text
Số điện thoại: 0901234567
Mật khẩu:      Password123!
```

Chế độ này không chứng minh database persistence và dữ liệu mất khi restart. Với
`APP_ENV=development`, tài khoản demo trên không tự được seed vào một database mới;
hãy đăng ký tài khoản qua UI hoặc dùng account đã được tạo trong database dev.

Alembic hỗ trợ tạo SQLite hoàn toàn mới cho local development; migration dùng batch
mode cho các foreign key cần recreate table trên SQLite.

## 7. Chạy ứng dụng đúng cách

Baseline cần đúng ba tiến trình. Mở ba terminal, tất cả bắt đầu tại root repository.

### Terminal 1 — Backend FastAPI

```bash
make livekit-backend
```

Backend phải ở `http://localhost:8000`. Kiểm tra:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/status
```

Kết quả status phải có `livekit_configured: true`.

Nếu báo port 8000 đã được dùng:

```bash
ss -ltnp 'sport = :8000'
```

Không mở backend thứ hai. Dừng tiến trình cũ bằng `Ctrl+C` tại terminal đã chạy nó.

### Terminal 2 — LiveKit worker

```bash
make livekit-worker
```

Giữ terminal này mở. Worker phải đăng ký với tên `alosm-voice`. Chỉ chạy **một**
worker baseline cho cùng developer/project khi test để tránh nhầm job giữa nhiều
worker.

Worker không chờ popup mới “khởi động service”: process chính đăng ký ngay khi lệnh
trên chạy và giữ một child process idle. Khi user nhấn nút gọi, frontend gọi
`POST /api/v1/livekit/prepare` để explicit-dispatch agent vào Room trong lúc popup
đang lazy-load. Micro chỉ bật sau consent. Nếu log báo early dispatch fail, token
dispatch tự fallback lúc browser join Room; browser cũng ngừng chờ prepare sau 1.5
giây để không chặn cuộc gọi.

### Terminal 3 — React frontend

```bash
make livekit-frontend
```

Mở `http://localhost:5173`, đăng nhập hoặc đăng ký, mở AloSM Assistant rồi bắt đầu
cuộc gọi. Cho phép microphone khi trình duyệt hỏi.

Backend hoặc worker đã thay đổi Python thì nên restart tiến trình tương ứng. Vite tự
reload frontend, nhưng thay `.env` luôn cần restart cả ba tiến trình.

## 8. Checklist test baseline

Trước hết kiểm tra happy path ngắn:

1. “Alo, tôi muốn đặt một xe máy.”
2. “Đón tôi ở Bến xe Mỹ Đình.”
3. “Tôi muốn đến Cầu Long Biên.”
4. Nghe agent đọc điểm đón, điểm đến, loại xe, giá và ETA.
5. “Đồng ý đặt xe.”
6. Kiểm tra UI có mã chuyến bắt đầu bằng `demo_`.

Sau đó kiểm tra flow có sửa thông tin:

1. “Tôi muốn đặt xe máy từ Phố cổ Hà Nội đến Cầu Long Biên.”
2. Khi agent hỏi xác nhận, nói: “Không, đổi điểm đón sang Đại học Ngoại thương.”
3. “Tôi đi hai người, đổi sang xe ô tô bốn chỗ.”
4. Kiểm tra agent báo giá lại sau khi đổi điểm đón và loại xe.
5. “Đồng ý đặt xe.”

Kiểm tra interruption/VAD riêng:

1. Chờ agent bắt đầu nói, ngắt bằng câu rõ dài hơn nửa giây.
2. Sau khi agent nói xong, đợi khoảng nửa giây rồi nói một câu địa điểm đầy đủ.
3. Theo dõi UI có transcript user hay không.
4. Nếu câu đầu mất nhưng nói lại mới nhận, ghi lại `call_id`, thời điểm và JSONL;
   đây là lỗi nhỏ còn mở của baseline.

## 9. Debug bằng JSONL

Chỉ bật transcript cho phiên local đã được phép debug:

```bash
LIVEKIT_DEBUG_EVENT_LOG=true \
LIVEKIT_DEBUG_TRANSCRIPTS=true \
make livekit-worker
```

Log nằm tại:

```text
logs/livekit/<call_id>.jsonl
```

Các event chính:

- `user_state_changed`: VAD/turn state của người dùng;
- `user_input_transcribed`: STT partial/final;
- `agent_state_changed`: listening/thinking/speaking;
- `overlapping_speech`: barge-in;
- `function_tools_executed`: tool nào đã chạy và có lỗi hay không;
- `conversation_item_added`: transcript/chat item và latency metrics;
- `error`, `close`: provider/session failure.

Phân biệt nhanh lỗi “không nghe”:

- Không có chuyển user state sang speaking: microphone/browser/input level.
- Có speaking nhưng không có `user_input_transcribed`: STT không tạo transcript.
- Có transcript partial nhưng không có `is_final=true`: endpoint/VAD/STT chưa chốt
  lượt nói; tiếng ồn nền là một khả năng.
- Có final transcript nhưng agent không thinking: kiểm tra error/tool event.

Logger mặc định không lưu raw audio, token, credential, tool arguments hoặc provider
payload. Sau khi debug xong, tắt lại hai biến debug.

## 10. Địa điểm baseline hỗ trợ

Hiện tại LiveKit booking tool **chỉ bảo đảm resolve 52 canonical place bên dưới**,
các alias ASR đã khai báo của chúng và một fuzzy match có độ tin cậy cao. Địa chỉ
tự do ngoài catalog chưa được gửi tới Nominatim/Google/Mapbox từ LiveKit tool.

Nếu tên không thuộc danh sách hoặc fuzzy score không đủ chắc chắn, agent phải hỏi
lại; không được tự coi một chuỗi bất kỳ là địa điểm hợp lệ.

1. VinUni
2. Hồ Gươm
3. Hồ Tây
4. Sân bay Nội Bài
5. Lăng Chủ tịch Hồ Chí Minh
6. Văn Miếu - Quốc Tử Giám
7. Quảng trường Ba Đình
8. Nhà hát Lớn Hà Nội
9. Ga Hà Nội
10. Bến xe Mỹ Đình
11. Bến xe Giáp Bát
12. Bến xe Nước Ngầm
13. Đại học Quốc gia Hà Nội
14. Đại học Bách khoa Hà Nội
15. Đại học Kinh tế Quốc dân
16. Đại học Ngoại thương
17. Đại học FPT Hà Nội
18. Học viện Nông nghiệp Việt Nam
19. Keangnam Landmark 72
20. Lotte Center Hà Nội
21. Vincom Center Bà Triệu
22. Vincom Mega Mall Times City
23. Vincom Mega Mall Royal City
24. AEON Mall Long Biên
25. AEON Mall Hà Đông
26. Sân vận động Mỹ Đình
27. Trung tâm Hội nghị Quốc gia
28. Cầu Long Biên
29. Cầu Nhật Tân
30. Cầu Vĩnh Tuy
31. Chợ Đồng Xuân
32. Phố cổ Hà Nội
33. Nhà thờ Lớn Hà Nội
34. Nhà tù Hỏa Lò
35. Hoàng thành Thăng Long
36. Bảo tàng Dân tộc học Việt Nam
37. Bảo tàng Hà Nội
38. Công viên Thủ Lệ
39. Công viên Yên Sở
40. Công viên Cầu Giấy
41. Vườn hoa Lý Thái Tổ
42. Chùa Một Cột
43. Chùa Trấn Quốc
44. Phủ Tây Hồ
45. Phố đi bộ Tràng Tiền
46. Vinhomes Ocean Park
47. Vinhomes Smart City
48. Bệnh viện Bạch Mai
49. Bệnh viện Việt Đức
50. Bệnh viện Trung ương Quân đội 108
51. Bệnh viện K Tân Triều
52. Tháp Rùa

Hai landmark có thêm điểm đón/trả cụ thể và bắt buộc chọn candidate:

- VinUni: Cổng chính VinUni, Cổng phụ VinUni, Cổng ký túc xá VinUni.
- Hồ Gươm: Đền Ngọc Sơn, Bưu điện Hà Nội, Quảng trường Đông Kinh Nghĩa Thục,
  Tượng đài Vua Lý Thái Tổ.

Nguồn dữ liệu runtime là `data/gazetteer/place_names.json`, alias nằm tại
`data/gazetteer/hanoi_place_aliases.json`, candidate nằm tại
`data/gazetteer/hanoi_landmark_pickup_points.json`.

## 11. Những gì đã làm được

- Thay audio path custom bằng LiveKit Room/WebRTC và AgentSession.
- Dùng pipeline streaming STT → LLM/tools → TTS.
- Dùng LiveKit-native VAD, endpointing và barge-in.
- Một `AloSMAgent` và một `BookingTask`, không dựng framework/multi-agent riêng.
- Function tools cho tìm/chọn địa điểm, chọn loại xe, báo giá, xác nhận, tạo booking,
  hủy flow và handoff.
- Chặn tạo chuyến nếu chưa có xác nhận rõ ràng.
- Cho phép sửa điểm đón, điểm đến, loại xe và báo giá lại.
- Token endpoint có auth; client không tự đặt room identity/metadata.
- State nghiệp vụ typed, sync realtime về UI và có thể lưu/khôi phục từ PostgreSQL.
- UI dùng frontend hiện có, có mic, speaker, transcript, text fallback, retry room và
  booking summary.
- JSONL observability có event/latency/tool status, privacy-safe mặc định.
- Feature flag giữ legacy runtime để rollback.
- Test backend/worker và frontend build đã pass tại baseline.

## 12. Session kết thúc và logout

- Gác máy là thao tác terminal: frontend gọi
  `POST /api/v1/sessions/{session_id}/end`, backend đánh dấu session `ENDED` và
  revoke bearer token hiện tại.
- Sau response, frontend xóa access token, user ID, user name và session ID khỏi
  localStorage, sau đó chuyển về `/login`.
- Nếu agent trả action `END_SESSION`, text và REST voice flow thực hiện cùng cleanup.
- Với LiveKit, transition từ connected sang disconnected cuối cùng cũng logout;
  trạng thái reconnect và disconnect có chủ đích để retry không logout.
- Đóng popup bằng nút `X` không kết thúc session và không logout.
- CTA “Đặt xe mới” reset conversation state; nó không dùng endpoint terminal.

## 13. Ưu điểm

- Giảm mạnh code tự quản lý audio transport, session và tool loop.
- Streaming realtime có latency tốt hơn kiểu upload cả utterance.
- Barge-in, room lifecycle, transcript và data channel dùng API chuẩn của framework.
- Nghiệp vụ AloSM tách khỏi media core, dễ test và thay provider.
- Có typed state và optimistic revision để tránh hai room ghi đè state.
- FE/BE cũ được tái sử dụng; migration có feature flag, không cần xóa legacy ngay.
- Log debug đủ phân biệt VAD, STT, LLM, TTS và tool mà không mặc định lưu audio/PII.

## 14. Nhược điểm và giới hạn hiện tại

- Baseline phụ thuộc LiveKit Cloud/Inference, Internet, quota và chi phí provider.
- Local dev cần ba tiến trình thay vì chỉ backend/frontend.
- Thỉnh thoảng VAD/STT bỏ sót lượt nói đầu, nhất là môi trường ồn; nói lại mới nhận.
- Enhanced noise cancellation/BVC chưa bật; hiện mới dùng auto gain control.
- Địa điểm giới hạn ở catalog 52 place; chưa có geocoder/routing production.
- Giá, ETA và booking ID hiện deterministic demo, chưa gọi fleet/dispatch thật.
- Kết quả `demo_*` được giữ trong voice state, chưa tạo một booking production qua
  `BookingService`/bảng `bookings`.
- Handoff mới tạo record, chưa chuyển audio vào operator room thực tế.
- Có thể gặp cold start/agent join chậm ở lần đầu; UI chỉ retry tự động một lần.
- LiveKit frontend chunk tương đối lớn; production build có cảnh báo chunk trên 500 kB.
- Fresh SQLite migration chain còn limitation cũ; full persistence nên dùng PostgreSQL
  dev đã migrate.
- Chưa có payment, live trip tracking, history/wallet và telephony SIP production.

## 15. Lỗi thường gặp

### `address already in use` ở port 8000

Một backend cũ vẫn chạy. Dùng terminal cũ và `Ctrl+C`; không khởi động backend thứ
hai.

### `Failed to fetch` khi login

Backend chưa chạy, sai `VITE_API_URL`, hoặc frontend đang mở từ origin không được
CORS cho phép. Kiểm tra `http://localhost:8000/health` trước.

### “Số điện thoại hoặc mật khẩu không đúng”

Ở `APP_ENV=development`, auth dùng database durable. Account demo in-memory không tự
tồn tại trong database mới. Đăng ký account qua UI hoặc dùng account dev đã seed.

### “Agent did not join the room”

Kiểm tra worker còn chạy, tên agent là `alosm-voice`, URL/key/secret cùng một project
và không có nhiều worker cấu hình lẫn nhau. Sau đó bấm **Tạo lại cuộc gọi**.

### UI hiện “Đang nghe” nhưng không có transcript

Kiểm tra quyền microphone/input device, thử tai nghe để giảm vọng, bật JSONL và xem
chuỗi `user_state_changed` → `user_input_transcribed`. Đây không đồng nghĩa backend
hoặc business tool bị lỗi.

### LiveKit báo quota adaptive interruption

Giữ `LIVEKIT_INTERRUPTION_MODE=vad`. Không bật `adaptive` cho baseline nếu chưa có
quyết định quota/cost.

## 16. Gate trước khi gửi thay đổi tiếp theo

```bash
uv run pytest -q tests/test_voice_agent \
  tests/test_backend/test_livekit_service.py \
  tests/test_api/test_livekit_routes.py \
  tests/test_backend/test_provider_safety.py

uv run ruff check src/voice_agent \
  src/backend/api/routes/livekit.py \
  src/backend/schemas/livekit.py \
  src/backend/services/livekit_service.py

cd src/frontend
npm run lint
npm run build
```

Ngoài automated gate, luôn chạy ít nhất một cuộc hội thoại thật, ghi lại `call_id`
và xác nhận frontend hiển thị đúng booking state.
