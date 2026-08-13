# Voice AI — Todo List (Sơ bộ + Chi tiết)

**Vai trò tài liệu:** Danh sách việc cần làm thực tế — dùng để giao việc, tạo branch, theo dõi PR.
**Bối cảnh, kiến trúc, chia 8 phần cho 4 người, nguyên tắc làm việc:** xem [voice_ai_overview.md](voice_ai_overview.md).
**Nhánh gốc Voice AI:** `feature/voice-ai` — tất cả PR voice merge vào đây, sau đó `feature/voice-ai` merge vào `develop`.
**Cập nhật:** 2026-08-10

---

## A. Sơ bộ — theo tuần

| Tuần | Số việc có branch | Mục tiêu |
|---|---|---|
| 1 — Foundation | 6 | Schemas, contracts, VAD, config, fake providers, gazetteer data |
| 2 — Core Build | 6 | Groq ASR, Edge-TTS, session, normalizer, formatter, confidence |
| 3 — Gateway & UI ⭐ | 3 | WebSocket gateway, API routes, Browser demo UI |
| 4 — Quality | 4 | Biasing, pronunciation, TTS cache |
| 5 — QA + Deploy | 0 (không có branch mới) | Test + đo latency + tuning + **thêm CD job vào `ci.yml`** |
| 6 — Demo Prep | 0 (không có branch mới) | Polish + kịch bản demo + test deploy production + README |

**Tổng:** 19 việc có branch · 8 việc QA/polish không có branch.

## B. Sơ bộ — theo 8 phần (chia cho 4 người)

| Phần | Chủ đề | Người phụ trách | Số việc có branch | Tuần chính |
|---|---|---|---|---|
| 1 | Audio Pipeline & VAD | Người | 1 | 1, 5 (tuning) |
| 2 | Session & Gateway | Người | 3 | 1, 2, 3 |
| 3 | ASR Core | Người | 2 (+ nửa contract) | 1, 2, 5 (tuning) |
| 4 | ASR Quality (địa danh, chuẩn hoá) | Người | 4 | 1, 2, 4 |
| 5 | TTS Core | Người | 1 (+ nửa contract) | 1, 2 |
| 6 | TTS Quality (phát âm, cache) | Người | 3 | 2, 4 |
| 7 | API Routes & Demo UI | Người | 2 | 3, 6 |
| 8 | Testing, QA & Demo Prep | Người | 1 | 1, 5, 6 |

*(Điền tên thật thay cho "Người 1–4" khi phân công — xem chi tiết vai trò từng phần ở `voice_ai_overview.md §5`.)*

---

## C. Chi tiết theo tuần

### Tuần 1 — Foundation

> Song song hoàn toàn. Assign cho nhiều người cùng lúc.

| Ref | Phần | Branch | Output file | Phụ thuộc | Người nhận | PR # | Trạng thái |
|---|---|---|---|---|---|---|---|
| S0-1 | 2 | `feature/voice-define-data-schemas` | `src/models/voice_schemas.py` | — | | | ✅ Code xong¹ |
| S0-2+3 | 3+5 | `feature/voice-define-asr-tts-contracts` | `src/voice/asr/base.py` · `src/voice/tts/base.py` | S0-1 merged | | | ✅ ASR contract dùng thật (Groq)¹; TTS contract vẫn chỉ scaffold — Phần 5 review trước khi implement Edge-TTS |
| S0-5 | 1 | `feature/voice-implement-vad-silero` | `src/voice/audio/vad.py` · `src/voice/audio/codec.py` | — | | | 🟡 Code xong¹ (EnergyVAD chạy được; Silero chưa test với model thật — xem `mustdo_voice.md`) |
| S0-7 | 2 | `feature/voice-add-config-voice-settings` | `src/config.py` *(mở rộng)* | — | | | ✅ Code xong¹ |
| S0-8 | 8 | `feature/voice-create-fake-providers-for-ci` | `tests/test_voice/fake_providers.py` | S0-2+3 merged | | | 🟡 Seed có sẵn¹ — Phần 8 mở rộng thêm kịch bản lỗi/timeout |
| S0-9 | 4 | `feature/voice-add-place-name-gazetteer` | `data/gazetteer/place_names.json` | — | | | 🟡 Seed 23 địa danh có sẵn¹ — **chưa phải danh sách thật AloSM**, xem `mustdo_voice.md` |

**Tiêu chí hoàn thành:** CI xanh với FakeASR + FakeTTS, schemas định nghĩa đủ field.

¹ *Code trực tiếp trên `feature/voice-ai` (không tách branch/PR riêng từng task) trong 3 phiên làm việc 2026-08-12: phiên 1 làm Phần 1+2 (S0-1, S0-5, S0-7, S0-6, S1-9); phiên 2 làm Phần 3+4 (S1-3, S1-5, S1-6, S0-9, S2-1, S2-2) + audit lại Phần 1+2; phiên 3 làm Phần 5-8 (đánh dấu ²). Việc tách lại thành PR riêng theo đúng git flow §E (nếu team muốn giữ lịch sử PR-per-task) là việc còn lại — xem `docs/mustdo_voice.md`.*

² *Phiên 3 (2026-08-12): Phần 5 (`edge_tts_provider.py`), Phần 6 (`formatter.py`, `pronunciation.py`, `cache.py`), Phần 7 (`demo/`, mount static + nối đủ Phần 3-6 vào `voice_routes.py`), Phần 8 (CI trigger thêm `feature/voice-ai`, `deploy.yml` scaffold, `FailingASRProvider`/`FailingTTSProvider`, `voice_local_dev.md`) — xem [prompt_voice_phan5_8.md](prompt_voice_phan5_8.md) cho prompt đã dùng.*

³ *Phiên 4 (2026-08-12): người dùng cung cấp `GROQ_API_KEY` thật, set vào `.env` (không track git). Verify bằng round-trip thật (edge-tts tạo audio → ffmpeg decode → `GroqASRProvider` thật) — phát hiện Whisper hallucinate câu hoàn chỉnh với confidence cao khi audio gần như im lặng; đã sửa bằng `utterance_rms()` pre-check (`config.py::voice_min_utterance_rms`) + `is_known_hallucination()` blocklist — xem `docs/mustdo_voice.md` §4 cho chi tiết đầy đủ.*

---

### Tuần 2 — Core Build

> Phụ thuộc Tuần 1 hoàn thành. Có thể làm song song trong tuần.

| Ref | Phần | Branch | Output file | Phụ thuộc | Người nhận | PR # | Trạng thái |
|---|---|---|---|---|---|---|---|
| S1-3 | 3 | `feature/voice-integrate-asr-groq` | `src/voice/asr/groq_provider.py` | S0-2+3 merged | | | ✅ Đã verify với `GROQ_API_KEY` thật³ (4/4 câu nhận đúng, confidence 0.93-0.98) — phát hiện + sửa 1 bug hallucination khi im lặng, xem `mustdo_voice.md` §4 |
| S1-4 | 5 | `feature/voice-integrate-tts-edge` | `src/voice/tts/edge_tts_provider.py` | S0-2+3 merged | | | ✅ Code xong² — **đã tự verify gọi Edge-TTS thật thành công** trong phiên phát triển |
| S0-6 | 2 | `feature/voice-implement-session-state-machine` | `src/voice/session.py` | S0-1 merged | | | ✅ Code xong¹ (Redis + InMemory fallback + BR-003) |
| S1-6 | 4 | `feature/voice-normalize-asr-transcript` | `src/voice/text/normalizer.py` | — | | | ✅ Code xong¹ (phạm vi có giới hạn, xem docstring trong file) |
| S1-7 | 6 | `feature/voice-format-text-for-tts-spoken` | `src/voice/tts/formatter.py` | — | | | ✅ Code xong² (số → chữ đọc, verify tay đủ trăm/nghìn/triệu) |
| S1-5 | 3 | `feature/voice-add-asr-confidence-gate` | `src/voice/asr/confidence.py` | S0-1 + S0-6 merged | | | ✅ Code xong¹ (risk-weighted, BR-001) |

> **Chốt cứng:** Chỉ build Groq (ASR) và Edge-TTS (TTS). Không build provider thứ 2, không so sánh.

---

### Tuần 3 — Gateway & Browser Demo UI ⭐

> **Tuần quan trọng nhất.** Cuối tuần 3: mở browser → nói → nghe AI trả lời.

| Ref | Phần | Branch | Output file | Phụ thuộc | Người nhận | PR # | Trạng thái |
|---|---|---|---|---|---|---|---|
| S1-9 | 2 | `feature/voice-wire-full-audio-pipeline` | `src/voice/gateway.py` | Tuần 2 tất cả merged | | | ✅ Code xong¹ (chạy với FakeASR/FakeTTS; ASR/TTS thật chờ S1-3/S1-4) |
| S1-10 | 7 | `feature/voice-expose-websocket-rest-routes` | `src/api/voice_routes.py` | S1-9 merged | | | ✅ Code xong² (nối đủ Phần 3-6, mount `demo/` static, `GET /health`) |
| NEW | 7 | `feature/voice-build-browser-demo-ui` | `demo/index.html` · `demo/demo.js` | S1-10 merged | | | ✅ Code xong² (AudioWorklet capture, phát audio qua `<audio>`+Blob URL) — **chưa test tay bằng mic/loa thật**, xem `mustdo_voice.md` |

**Demo UI cần có:**
- Nút "Gọi" / "Kết thúc"
- Hiển thị trạng thái: 🎙️ Đang nghe / ⚙️ Đang xử lý / 🔊 AI đang nói
- Transcript realtime (người dùng nói gì, AI nói gì)
- Không cần đẹp phức tạp — clean, dễ nhìn khi trình chiếu

**Acceptance criteria Demo UI (Definition of Done — Tuần 3):**
- **Production (deploy):** Chạy qua **HTTPS** trên PaaS (Render/Railway/Fly.io) — HTTPS tự động, mic hoạt động không cần thêm cấu hình.
- **Local dev:** `http://localhost` vẫn được (Chrome cho phép mic trên localhost không cần HTTPS).
- Trình duyệt ưu tiên: **Chrome / Edge** (Chromium-based) — không bắt buộc hỗ trợ Firefox / Safari
- Không cần responsive / mobile — tối ưu cho màn hình laptop khi trình chiếu
- Không cần reload trang giữa các lượt gọi — session vẫn giữ được qua WebSocket reconnect

---

### Tuần 4 — Quality (địa danh + cache)

| Ref | Phần | Branch | Output file | Phụ thuộc | Người nhận | PR # | Trạng thái |
|---|---|---|---|---|---|---|---|
| S2-1 | 4 | `feature/voice-load-place-name-gazetteer` | `src/voice/text/gazetteer.py` | S0-9 merged | | | ✅ Code xong¹ |
| S2-2 | 4 | `feature/voice-bias-asr-with-place-names` | `src/voice/asr/biasing.py` | S2-1 merged | | | ✅ Code xong¹ (word-aligned fuzzy match, đã tự phát hiện + sửa 1 bug "ăn" nhầm từ hàng xóm khi viết test) |
| S2-3 | 6 | `feature/voice-override-tts-pronunciation` | `src/voice/tts/pronunciation.py` | S2-1 merged | | | ✅ Code xong² |
| S2-4 | 6 | `feature/voice-cache-static-tts-phrases` | `src/voice/tts/cache.py` | S1-4 merged | | | ✅ Code xong² (`CachingTTSProvider` decorator + prewarm lúc app khởi động) |

---

### Tuần 5 — QA + Deploy (không có branch mới)

| Việc | Phần | Người làm |
|---|---|---|
| Test E2E: gọi → đặt xe → xác nhận → kết quả | 8 | Cả team |
| Đo latency p50/p95 → mục tiêu ≤ 2.5s | 8 | Phần 8 + Phần 1/3/5 hỗ trợ |
| Test F2: fail 2 lần → handoff | 8 | Phần 8 |
| Test F3: hỏi vị trí xe | 8 | Phần 8 |
| Tuning `asr_confidence_threshold` | 3 | Người 2 |
| Tuning `vad_silence_threshold_ms` | 1 | Người 1 |
| Mở rộng `ci.yml` thêm `deploy` job (CD lên PaaS) | 8 | 🟡 Scaffold có sẵn² (`.github/workflows/deploy.yml`, `workflow_dispatch` — chưa điền PaaS/secret thật) |
| Cấu hình biến môi trường trên PaaS (GROQ\_API\_KEY, REDIS\_URL, APP\_ENV=production) | 8 | Phần 8 |
| Fix bug phát hiện khi QA | (theo phần bị lỗi) | Người phụ trách phần đó |

---

### Tuần 6 — Demo Prep (không có branch mới)

| Việc | Phần | Người làm |
|---|---|---|
| Polish demo UI (font, màu, trạng thái rõ hơn) | 7 | Người 4 |
| Chuẩn bị 3 kịch bản demo (đặt xe thành công / ASR fail → handoff / tra cứu chuyến) | 7 + 8 | Cả team |
| Test deploy production: HTTPS mic, WebSocket qua PaaS, Redis session | 8 | Phần 8 |
| Viết README hướng dẫn chạy local và link URL production | 8 | ✅ Phần local xong² ([voice_local_dev.md](voice_local_dev.md)) — phần link production chờ deploy thật |
| Buffer cho sự cố | — | Cả team |

---

## D. Sơ đồ phụ thuộc toàn bộ branch

**Cấu trúc nhánh (cần biết):**
```
main  ← release + deploy production
  └ develop  ← tích hợp chung toàn project (tất cả feature → đây)
      └ feature/voice-ai  ← nhánh gốc Voice AI (Voice lead quản lý)
          └ feature/voice-*  ← các nhánh task phân công (↓ sơ đồ dưới)
```
> **G1** chỉ để báo cáo — không phải nhánh làm việc.

**Sơ đồ phụ thuộc:**
```
feature/voice-ai  ← nhánh gốc Voice AI (merge vào develop)
│
├── [Tuần 1 — song song]
│   ├── feature/voice-define-data-schemas                (Phần 2)
│   ├── feature/voice-implement-vad-silero                (Phần 1)
│   ├── feature/voice-add-config-voice-settings           (Phần 2)
│   ├── feature/voice-add-place-name-gazetteer            (Phần 4)
│   ├── feature/voice-define-asr-tts-contracts            (Phần 3+5) ← chờ define-data-schemas
│   └── feature/voice-create-fake-providers-for-ci        (Phần 8)  ← chờ define-asr-tts-contracts
│
├── [Tuần 2 — song song]
│   ├── feature/voice-integrate-asr-groq                  (Phần 3)
│   ├── feature/voice-integrate-tts-edge                  (Phần 5)
│   ├── feature/voice-implement-session-state-machine     (Phần 2)
│   ├── feature/voice-normalize-asr-transcript            (Phần 4)
│   ├── feature/voice-format-text-for-tts-spoken          (Phần 6)
│   └── feature/voice-add-asr-confidence-gate             (Phần 3)
│
├── [Tuần 3 — có thứ tự]
│   ├── feature/voice-wire-full-audio-pipeline            (Phần 2) ← chờ tuần 2 xong
│   ├── feature/voice-expose-websocket-rest-routes        (Phần 7) ← chờ gateway
│   └── feature/voice-build-browser-demo-ui               (Phần 7) ← chờ routes
│
└── [Tuần 4 — song song]
    ├── feature/voice-load-place-name-gazetteer           (Phần 4)
    ├── feature/voice-bias-asr-with-place-names           (Phần 4) ← chờ gazetteer loader
    ├── feature/voice-override-tts-pronunciation          (Phần 6) ← chờ gazetteer loader
    └── feature/voice-cache-static-tts-phrases            (Phần 6)
```

---

## E. Lệnh Git nhanh cho dev

```bash
# Tạo branch từ feature/voice-ai
git checkout feature/voice-ai && git pull origin feature/voice-ai
git checkout -b feature/voice-<mô-tả>

# Push + mở PR vào feature/voice-ai
git push -u origin feature/voice-<mô-tả>

# Sync với feature/voice-ai khi đang làm
git fetch origin && git rebase origin/feature/voice-ai
```

Checklist review PR, Definition of Done, nguyên tắc test-double: xem [voice_ai_overview.md §7](voice_ai_overview.md). Phương án kỹ thuật đã chốt cho từng phần: [voice_ai_overview.md §6](voice_ai_overview.md).

---

*Tài liệu này do Voice AI lead duy trì — cập nhật hàng tuần khi giao việc/merge PR. Bối cảnh và lý do scope cut: [voice_ai_overview.md](voice_ai_overview.md).*
