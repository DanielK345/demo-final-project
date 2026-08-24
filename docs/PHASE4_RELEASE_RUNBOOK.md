# Phase 4 product release runbook

Runbook này dành cho người/agent chạy kiểm chứng. Code owner không chạy provider,
không thay secret và không sửa `.env` production trong bước review.

## 1. Cấu hình runtime production-like

Lấy connection string từ nút **Connect** của đúng Supabase project. Backend và
LiveKit worker là process persistent nên dùng Direct khi hạ tầng hỗ trợ IPv6, hoặc
Supavisor Session Pooler port `5432` trên mạng IPv4. Không dùng transaction pooler
`6543` cho baseline này.

```dotenv
DATABASE_URL=postgresql://postgres.PROJECT_REF:PASSWORD@REGION.pooler.supabase.com:5432/postgres
DATABASE_POOL_MODE=auto
DATABASE_POOL_SIZE=5
DATABASE_POOL_MAX_OVERFLOW=5
DATABASE_POOL_TIMEOUT_SECONDS=5
DATABASE_POOL_RECYCLE_SECONDS=300

# Ưu tiên Direct cho Alembic. Nếu máy chạy migration chỉ có IPv4, dùng Session
# Pooler 5432; không dùng Transaction Pooler 6543 cho migration nhiều statement.
DATABASE_URL_MIGRATIONS=postgresql://postgres:PASSWORD@db.PROJECT_REF.supabase.co:5432/postgres

LIVEKIT_DELETE_ROOM_ON_CLOSE=false
LIVEKIT_STATE_RESTORE_TIMEOUT_SECONDS=10
```

Không đưa password, service-role key hay Google credential vào frontend.

## 2. Khởi động ba process

Terminal 1:

```bash
make livekit-backend
```

Terminal 2, thay `RUN_ID` bằng timestamp duy nhất:

```bash
LIVEKIT_DEBUG_EVENT_LOG=true \
LIVEKIT_DEBUG_TRANSCRIPTS=false \
LIVEKIT_DEBUG_LOG_DIR=logs/livekit/RUN_ID \
make livekit-worker
```

Terminal 3:

```bash
make livekit-frontend
```

## 3. Durable booking gate — 10 runs

Runner dùng LiveKit Room/text input thật và gọi pipeline LLM/tools/TTS thật. Mỗi
attempt tạo một `LIVEKIT_SMOKE` session. Một attempt chỉ PASS khi state LiveKit
khớp cả ba hàng authoritative trong `ride_sessions`, `fare_quotes` và `bookings`.
Evidence mới dùng smoke schema `2`; schema `1` là baseline lịch sử chưa có DB checks.

```bash
uv run python -m scripts.livekit_room_smoke \
  --booking \
  --runs 10 \
  --output reports/voice-evaluation/phase4-product/RUN_ID/connection-results.jsonl
```

Aggregate đúng log directory của run, không trộn log cũ:

```bash
uv run python -m scripts.aggregate_livekit_evaluation \
  --log-dir logs/livekit/RUN_ID \
  --smoke-results reports/voice-evaluation/phase4-product/RUN_ID/connection-results.jsonl \
  --dataset-version phase4-product-v1 \
  --run-id RUN_ID \
  --output-dir reports/voice-evaluation/phase4-product/RUN_ID
```

Gate:

- process exit code `0`, `LIVEKIT_SMOKE_SUMMARY=10/10`;
- `business-invariants.json`: `passed=true`, `violation_count=0`;
- mỗi attempt có sáu check `durable_* = true`;
- không `STATE_CONFLICT`, duplicate booking hoặc booking thiếu confirmation;
- giữ nguyên raw JSONL khi báo lỗi, không chỉ gửi ảnh màn hình.

## 4. Browser/device gate

Chạy lần lượt, ghi `session_id`, browser/device và kết quả vào release ticket:

1. Chrome laptop + mic máy: happy path.
2. Edge/Chrome laptop + headset: happy path và barge-in.
3. Một mobile browser: permission, mute/unmute, background/foreground.
4. Throttle/offline ngắn rồi online lại: chờ LiveKit native reconnect; nếu Session
   vẫn disconnected, UI chỉ tạo một Room mới và khôi phục cùng durable session.
5. Hai tab: tab cũ không được ghi đè revision của tab mới; không booking trùng.
6. Sau khi booking thành công, disconnect không được tự retry booking.

## 5. Offline Vietnamese ASR gate

Tạo JSONL manifest, audio đặt trong controlled storage. Không commit audio/PII.

```json
{"case_id":"north-quiet-001","dataset_version":"vi-places-v1","audio_path":"audio/north-quiet-001.wav","audio_sha256":"64_HEX_CHARS","consent":true,"expected_transcript":"Tôi muốn đi từ VinUni đến Bưu điện Hà Nội","expected_entities":["VinUni","Bưu điện Hà Nội"],"accent":"north","noise":"quiet"}
```

Chạy cùng STT factory mà worker dùng (`Google chirp_2`, `vi-VN` theo baseline):

```bash
uv run python -m scripts.benchmark_livekit_asr \
  --manifest CONTROLLED_PATH/manifest.jsonl \
  --output-dir reports/voice-evaluation/vi-places-v1/RUN_ID
```

Runner từ chối case thiếu `consent`, hash audio sai, duplicate `case_id` hoặc output
directory đã có evidence. Review `asr-results.jsonl` và `asr-summary.json` theo
accent/noise; khóa threshold trước khi quyết định release.

## 6. Test/build commands cho agent kiểm chứng

```bash
uv run pytest -q \
  tests/test_voice_agent/test_server.py \
  tests/test_voice_agent/test_persistence.py \
  tests/test_voice_agent/test_booking_state.py \
  tests/test_scripts/test_livekit_room_smoke.py \
  tests/test_scripts/test_livekit_evaluation.py \
  tests/test_scripts/test_livekit_asr_benchmark.py \
  tests/test_api/test_livekit_routes.py \
  tests/test_backend/test_livekit_service.py
```

```bash
uv run ruff check \
  src/voice_agent \
  scripts/livekit_room_smoke.py \
  scripts/aggregate_livekit_evaluation.py \
  scripts/benchmark_livekit_asr.py \
  tests/test_voice_agent \
  tests/test_scripts
```

```bash
cd src/frontend
npm run build
npm run lint
```

Không báo release chỉ dựa trên unit tests. Cần kèm durable 10-run, browser matrix và
ASR artifact. Model A/B không nằm trên critical path cho đến khi ba gate này PASS.
