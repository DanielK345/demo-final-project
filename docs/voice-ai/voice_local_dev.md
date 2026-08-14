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

Mặc định (không sửa `.env`) vẫn chạy được: ASR dùng `FakeASRProvider` (transcript giả),
TTS dùng `EdgeTTSProvider` thật (miễn phí). Muốn ASR thật:

```env
GROQ_API_KEY=sk-...   # free tại console.groq.com
```

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

Test Voice **không gọi Groq/Edge-TTS thật** dù `.env` có `GROQ_API_KEY` thật (guard
bằng biến `PYTEST_CURRENT_TEST` — xem `src/backend/api/routes/voice.py`).
