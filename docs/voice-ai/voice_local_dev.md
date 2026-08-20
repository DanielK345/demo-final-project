# Legacy Voice AI — local rollback runbook

> Trạng thái `LEGACY_ROLLBACK`. Để chạy LiveKit baseline, dùng
> [`../LIVEKIT_TEAM_SETUP.md`](../LIVEKIT_TEAM_SETUP.md). Không dùng runbook này cho
> Phase 4 trừ khi chạy flow cũ làm đối chứng A/B.

Hướng dẫn chạy legacy runtime. Kiến trúc: [voice-runtime-architecture.md](voice-runtime-architecture.md).
External/release blockers: [mustdo.md](../../mustdo.md).

## 1. Cài đặt

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env
```

Runtime không tạo transcript giả. Cấu hình provider thật trước khi thử voice:

```env
# LLM/Transcript rewrite qua OpenRouter
OPENROUTER_API_KEY=...
AGENT_LLM_MODEL=openai/gpt-5.6-luna-pro
AGENT_LLM_BASE_URL=https://openrouter.ai/api/v1
VOICE_TRANSCRIPT_REWRITE_ENABLED=true
VOICE_TRANSCRIPT_REWRITE_MODEL=openai/gpt-5.6-luna-pro
VOICE_TRANSCRIPT_REWRITE_BASE_URL=https://openrouter.ai/api/v1

# Speech provider độc lập
OPENAI_API_KEY=...                    # chỉ khi dùng OpenAI STT/TTS cho /voice/turn
GROQ_API_KEY=...                      # /voice/stream Groq ASR
VOICE_STT_MODEL=gpt-4o-transcribe
```

Thiếu `GROQ_API_KEY`, WebSocket ASR trả lỗi cấu hình rõ ràng. Thiếu/sai `OPENROUTER_API_KEY`,
live rewrite gate fail thật và transcript được giữ nguyên an toàn; không fallback sang fake provider.
OpenRouter key không được dùng thay OpenAI Speech key.

## 2. Chạy server

```bash
make run
# hoặc: uvicorn src.main:app --reload
```

- API Backend: `http://localhost:8000/api/v1/...` (đã có sẵn, không đổi)
- Voice health: `http://localhost:8000/api/v1/voice/health`
- **Demo UI:** `http://localhost:8000/demo/`

## 3. Thử demo UI

1. Mở `http://localhost:8000/demo/` bằng **Chrome/Edge**.
2. Bấm **"Gọi"** → cho phép quyền mic.
3. Nói câu đặt xe tự nhiên. Backend chuyển transcript qua Core Agent model/tool loop;
   booking vẫn cần địa điểm đã resolve và explicit confirmation:
   - *"Tôi muốn đặt xe"*
   - *"Từ Vincom Đồng Khởi đến Landmark 81"*
   - *"Đúng"* (xác nhận đặt xe) / *"Thôi"* (huỷ)
4. Bấm **"Kết thúc"** để dừng.

## 4. Chạy test

```bash
pytest tests/ -v          # toàn repo — phải xanh hết, kể cả test cũ của BE/agentic
ruff check src tests scripts
```

Các unit/regression test kiểm tra state và guardrail độc lập. Bài full WebSocket chỉ chạy khi
`VOICE_LIVE_PCM16_FIXTURE` trỏ tới PCM16 16 kHz có giọng nói thật và consent. Kiểm tra LLM thật:

```powershell
.\.venv\Scripts\python.exe scripts/live_voice_rewrite_check.py
```

Provider/authentication failure làm live gate fail; không được đổi thành pass bằng mock.

## 5. ASR ZipFormer local

Pipeline ZipFormer CPU production, API, biến môi trường, Docker và số benchmark thật nằm tại
[zipformer-asr.md](zipformer-asr.md). Chạy theo thứ tự:

```powershell
.\.venv\Scripts\python.exe scripts\prepare_zipformer_model.py
.\.venv\Scripts\python.exe scripts\live_zipformer_check.py
.\.venv\Scripts\python.exe scripts\benchmark_zipformer.py
```

Đặt `VOICE_PROVIDER=zipformer` nếu muốn bắt buộc `/api/v1/voice/turn` dùng STT local. Ở chế độ `auto`,
Voice flow ưu tiên ZipFormer khi `/health/ready` đã sẵn sàng; frontend vẫn chỉ gọi Voice API và không phụ
thuộc tên file ONNX/runtime.
