# TTS output runtime và acceptance

Cập nhật: **2026-08-16** · Trạng thái: `CURRENT`.

## Runtime contract

`TTSOrchestrator` là đường synthesis duy nhất cho `/turn`, `/speak`, WebSocket và
typed reply. Pipeline:

```text
Agent/backend text
  -> deterministic output reviewer
  -> spoken formatter/pronunciation
  -> timeout + retry + circuit breaker + voice fallback
  -> provider audio
  -> FFprobe/FFmpeg validation
  -> cache/metrics/result metadata
```

## Output review

Reviewer trả `ALLOW`, `REWRITE`, `BLOCK` hoặc `HANDOFF` và kiểm tra:

- PII, secret, URL và dữ liệu nội bộ;
- booking success chưa có confirmed backend state;
- giá, voucher, địa chỉ, phủ định và critical identifiers;
- safety/handoff;
- lời hứa hoàn tiền/bồi thường/cam kết do LLM tự tạo.

TTS không được nói “đặt xe thành công” chỉ vì model viết như vậy.

## Reliability

- Per-attempt timeout: 12 giây mặc định.
- Request deadline: 30 giây mặc định.
- Retry hữu hạn theo voice.
- Primary mặc định `vi-VN-HoaiMyNeural`, fallback
  `vi-VN-NamMinhNeural`.
- Circuit breaker, bounded concurrency/queue.
- Cache TTL/LRU hữu hạn chỉ cho prewarm phrase an toàn; dynamic PII không cache mặc định.
- Empty/corrupt/invalid audio trả typed TTS error, không trả audio rỗng.

Mọi giá trị có thể override bằng ENV trong `.env.example`.

## Audio technical gate

Mỗi output được decode thật và kiểm tra MIME/codec/sample rate/channel/duration,
size, RMS, peak, silence ratio, clipping và truncation. Validation dùng source
metadata từ FFprobe và PCM decode từ FFmpeg.

## Frontend playback

- Server audio được tạo Blob/object URL và validate MIME/empty payload.
- Audio cũ dừng khi lượt mới, mute hoặc unmount.
- Playback error hiển thị; có tối đa một lần server regeneration.
- Fallback voice được báo qua metadata/UI.
- Không fallback ngầm sang browser speech synthesis.

## Health, metrics và live acceptance

- `/api/v1/voice/tts/health`
- `/api/v1/voice/tts/metrics`
- Headers: `X-TTS-Provider`, `X-TTS-Voice`, `X-TTS-Fallback`,
  `X-TTS-Duration-Ms`, `X-TTS-Review`.

Chạy live gate:

```powershell
.\.venv\Scripts\python.exe scripts\live_tts_output_check.py
```

Evidence hiện hành: [`tts-output-live-report.json`](tts-output-live-report.json).
Lần gate đã lưu: 4/4 corpus case pass, error rate 0, mean WER `0.1402`, mean CER
`0.058`; HoaiMy và NamMinh vượt technical gate.

## Release gates chưa tự động hóa

- ít nhất hai reviewer tiếng Việt nghe và ký duyệt;
- provider production có SLA/quota/DPA/quyền thương mại;
- device/browser/audio-output matrix;
- load/soak và provider outage drill.

Các bước, owner và evidence cần nộp nằm tại `mustdo.md` mục TTS.
