# Voice AI — Chạy thử ở local (project thật, có BE/FE/agentic)

Hướng dẫn nhanh cho project đã tích hợp Voice AI — xem
[prompt_voice_integration_real_be_fe.md](prompt_voice_integration_real_be_fe.md) cho kiến
trúc đầy đủ, [mustdo_voice.md](mustdo_voice.md) cho việc còn thiếu.

## 1. Cài đặt

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env
```

Runtime không tạo transcript giả. Cấu hình provider thật trước khi thử voice:

```env
OPENAI_API_KEY=...                    # /voice/turn, transcript rewrite và OpenAI TTS
GROQ_API_KEY=...                      # /voice/stream Groq ASR
VOICE_STT_MODEL=gpt-4o-transcribe
VOICE_TRANSCRIPT_REWRITE_ENABLED=true
VOICE_TRANSCRIPT_REWRITE_MODEL=gpt-5.6-luna
```

Thiếu `GROQ_API_KEY`, WebSocket ASR trả lỗi cấu hình rõ ràng. Thiếu hoặc sai
`OPENAI_API_KEY`, `/voice/turn`/live rewrite gate fail thật; không fallback sang fake provider.

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
3. Nói mẫu câu mà `SessionService` hiểu được (dialogue engine hiện tại là rule-based,
   xem `src/backend/services/session_service.py` để biết đúng mẫu câu):
   - *"Tôi muốn đặt xe"*
   - *"Từ Vincom Đồng Khởi đến Landmark 81"*
   - *"Đúng"* (xác nhận đặt xe) / *"Thôi"* (huỷ)
4. Bấm **"Kết thúc"** để dừng.

## 4. Chạy test

```bash
pytest tests/ -v          # toàn repo — phải xanh hết, kể cả test cũ của BE/agentic
ruff check src/ tests/
```

Các unit/regression test kiểm tra state và guardrail độc lập. Bài full WebSocket chỉ chạy khi
`VOICE_LIVE_PCM16_FIXTURE` trỏ tới PCM16 16 kHz có giọng nói thật và consent. Kiểm tra LLM thật:

```powershell
.\.venv\Scripts\python.exe scripts/live_voice_rewrite_check.py
```

Provider/authentication failure làm live gate fail; không được đổi thành pass bằng mock.
