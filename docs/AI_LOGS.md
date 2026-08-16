# AI Logs — kết nối và vận hành

Cập nhật: **2026-08-16**.

## Trạng thái

- Hook config hợp lệ cho Claude, Codex, Cursor, Gemini và GitHub Copilot.
- Git `pre-push` hook đã được cài.
- `AI_LOG_SERVER`, `AI_LOG_API_KEY`, `AI_LOG_DIR` có trong `.env` local.
- DNS/TLS/HTTP tới `ai-logs.note.transformerlabs.ai/api/ingest` hoạt động.
- Authenticated empty-batch canary trả HTTP `202`; credential được endpoint chấp nhận.
- Queue local còn 392 entry. Chưa xuất queue này trong lần reconnect vì nó chứa
  prompt/tool response của project và cần phê duyệt rõ trước khi truyền ra ngoài.

## Luồng dữ liệu

```text
IDE/AI hook
  -> scripts/log_hook.py
  -> recursive secret redaction
  -> .ai-log/session.jsonl
  -> scripts/submit_log.py
  -> redaction lần hai
  -> POST /api/ingest
  -> archive local chỉ chứa payload đã redaction
```

`scripts/ai_log_privacy.py` redaction nested secret fields, OpenAI/OpenRouter key,
Bearer token, GitHub token và credential assignment. `token_budget`, token count và
nội dung không phải credential được giữ nguyên.

## Cài lại hook

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```

Kiểm tra:

```powershell
Get-Content .git\hooks\pre-push
.\.venv\Scripts\python.exe scripts\submit_log.py --help
```

## Submit

Chế độ hook mặc định không chặn `git push`: lỗi mạng/auth sẽ giữ nguyên queue.

```powershell
.\.venv\Scripts\python.exe scripts\submit_log.py
```

Khi cần nghiệm thu kết nối, dùng strict mode; lệnh trả non-zero nếu server lỗi:

```powershell
.\.venv\Scripts\python.exe scripts\submit_log.py --strict
```

Lưu ý: hai lệnh trên gửi prompt/tool response đang chờ lên server cấu hình trong
`.env`. Chỉ chạy sau khi owner xác nhận endpoint, quyền chia sẻ và retention.

## Failure behavior

- Network/auth/server fail: pending batch được merge trở lại `session.jsonl`.
- Thành công: chỉ entry đã redaction được append vào archive theo ngày.
- Trên 500 entry: gửi batch cũ nhất, phần còn lại giữ cho lần sau.
- Hook không tìm thấy Python: không chặn IDE/git; cần sửa Python PATH rồi chạy lại.

Không commit `.env`, `.ai-log/session.jsonl`, archive hay API key.
