# Ghi chú kiến trúc: hiện có 2 hệ thống Voice AI song song

Cập nhật 13/08/2026, trong lúc reorganize project. Ghi lại rõ để không ai (kể cả AI
agent phiên sau) hiểu nhầm 1 trong 2 là "code chết".

## Hiện trạng

| | `POST /api/v1/voice/turn` | `WS /api/v1/voice/stream` + `POST /api/v1/voice/speak` |
|---|---|---|
| Tác giả | DanielK345 (`test_speech_model`) | Voice AI (session trước) |
| Provider | OpenAI `gpt-4o-transcribe`/TTS hoặc Gemini STT | Groq Whisper + Edge-TTS |
| Cơ chế | 1 lần gọi: upload cả đoạn ghi âm → nhận transcript + text + audio (base64) | Streaming thời gian thực qua WebSocket, audio gửi từng chunk |
| Frontend đang gọi? | **CÓ** — `AssistantPage.tsx` → `features/voice/api.ts::sendVoiceTurn()`, đây là nút micro thật trên web hiện tại | **KHÔNG** — không còn chỗ nào trong `src/frontend/src` gọi `/stream` hay `/speak` nữa |
| Code Backend | `src/backend/services/voice_service.py`, `src/backend/integrations/voice_client.py`, `src/backend/schemas/voice.py` | `src/voice/` (toàn bộ package: gateway, ASR/TTS provider, VAD, normalizer, gazetteer...) |
| Test | `tests/test_api/test_voice_routes.py` | `tests/test_voice/*` |

Cả hai đường hiện dùng chung post-ASR policy: gazetteer/normalizer, PII masking, OpenAI Structured Outputs và semantic guard trong `transcript_rewriter.py`. Không đường production nào tạo transcript giả.

Cả 2 route cùng sống trong `src/backend/api/routes/voice.py` (không đè nhau, khác
path) sau khi phát hiện gỡ `/turn` làm micro trên web lỗi 404 thật.

## Vì sao lại có 2 hệ thống

`/turn` được build cùng lúc cả BE lẫn FE trong 1 commit (`5e8a1d5 "test whisper
model"`) — tại thời điểm đó chưa biết/chưa phối hợp với hệ thống WS Gateway đã có sẵn.
Do route trùng path (`/voice.py`), commit đó **ghi đè hoàn toàn** file cũ thay vì thêm
route mới, khiến app không boot được (`main.py` import 1 hàm không còn tồn tại) —
phát hiện và khôi phục lại (giữ cả 2) trong lúc rà soát này.

## Việc cần quyết định (không tự làm — quyết định sản phẩm)

Về lâu dài, duy trì 2 hệ thống Voice AI song song (2 provider, 2 kiến trúc streaming
khác nhau, 2 bộ test) là gánh nặng bảo trì không cần thiết. Team nên chọn 1:

- **Chọn `/turn` (OpenAI/Gemini)**: đơn giản hơn (không cần WebSocket/VAD/streaming),
  nhưng độ trễ cao hơn (chờ ghi âm xong cả câu mới gửi), phụ thuộc OpenAI/Gemini
  (có phí, cần key thật).
- **Chọn `/stream`+`/speak` (Groq+Edge-TTS)**: độ trễ thấp hơn (streaming, ngắt câu tự
  động qua VAD), miễn phí (Edge-TTS không cần key, Groq có free tier), nhưng kiến trúc
  phức tạp hơn, cần nối lại vào `AssistantPage.tsx` (hiện chưa gọi).
- **Giữ cả 2** nếu có lý do sản phẩm rõ ràng (vd fallback provider).

Sau khi chọn, xoá hệ thống còn lại (code + test + route) — không nên để tồn tại mãi
"phòng khi cần" (xem nguyên tắc dọn code chết trong yêu cầu reorganize).
