# Kế hoạch chuẩn hóa transcript Voice AI bằng LLM

## Kết luận kiến trúc

Pipeline đích:

```text
Audio thật
  -> VAD/endpointing (nếu dùng WebSocket)
  -> ASR thật + language/prompt glossary
  -> sửa địa danh deterministic từ gazetteer
  -> chuẩn hóa số/chính tả deterministic hiện có
  -> che PII thành placeholder bất biến
  -> OpenAI Responses API + Structured Outputs
  -> guardrail bảo toàn ý nghĩa/placeholder/xác nhận
  -> khôi phục PII trong process
  -> Core Agent
  -> TTS thật
```

Không dùng LLM rewrite để “đoán lại audio”. LLM chỉ sửa văn bản khi bằng chứng trong
transcript đủ rõ. Nếu model lỗi, không chắc chắn hoặc thay đổi ý nghĩa, pipeline giữ nguyên
transcript trước rewrite.

## Vì sao chọn hai tầng

1. Cải thiện ngay tại ASR giảm lỗi tốt hơn việc cố cứu một transcript đã mất thông tin.
   OpenAI hỗ trợ `prompt` để tăng nhận dạng tên riêng và từ chuyên ngành. Tài liệu hiện hành
   cũng mô tả hậu xử lý transcript bằng text model.
2. Rule-based vẫn phù hợp cho phép đổi số và gazetteer nhỏ, nhưng không đủ cho lỗi đồng âm,
   thiếu dấu và tách từ tiếng Việt.
3. LLM rewrite xử lý phần ngôn ngữ mềm; guardrail deterministic giữ các invariant nghiệp vụ.

Nguồn chính thức:

- [OpenAI file transcription và post-processing](https://developers.openai.com/api/docs/guides/speech-to-text)
- [GPT-4o Transcribe](https://developers.openai.com/api/docs/models/gpt-4o-transcribe)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-5.6 prompting guidance](https://developers.openai.com/api/docs/guides/model-guidance?model=gpt-5.6)

## Quyết định kỹ thuật

- ASR mặc định cho `/voice/turn`: `gpt-4o-transcribe`.
- Rewrite mặc định: `gpt-5.6-luna`, reasoning `none`, timeout 5 giây.
- Structured schema gồm `normalized_text`, `meaning_preserved`,
  `requires_clarification`, `confidence`, `change_types`.
- Không gửi conversation history. Context chỉ gồm `current_workflow` và `current_step`.
- Email, chuỗi số, số điện thoại, thời gian và mã chữ-số được thay bằng placeholder trước
  request; `store=false`; `safety_identifier` là hash session ID.
- Không nâng hoặc tự bịa STT confidence. `/voice/turn` trả `null` khi provider không cung cấp.
- LLM không được sửa semantic confirmation ở bước `CONFIRM`.
- Rewrite bị từ chối nếu placeholder thay đổi, similarity quá thấp, số token lệch quá lớn,
  model báo không bảo toàn nghĩa, cần hỏi lại hoặc confidence dưới ngưỡng.

## Hai runtime được tích hợp

### `POST /api/v1/voice/turn`

Frontend hiện sử dụng route này. Audio được transcription thật, qua toàn bộ normalization và
rewrite trước khi gửi tới `SessionService`. Response công khai transcript cuối cùng cùng metadata
rewrite, không trả transcript thô.

### `WS /api/v1/voice/stream`

Groq ASR nhận prompt từ gazetteer. Rewrite chỉ chạy khi ASR confidence tối thiểu 0.45. Event
`transcript` trả transcript cuối cùng và metadata rewrite. Khi thiếu `GROQ_API_KEY`, runtime dùng
provider “unavailable” trả lỗi rõ ràng; không dùng FakeASR trong production.

## Đánh giá không mock

Chạy:

```powershell
.\.venv\Scripts\python.exe scripts/live_voice_rewrite_check.py
```

Script gọi OpenAI thật và fail nếu credential/model lỗi, PII không được bảo toàn hoặc các case
đại diện không đạt. Không chuyển lỗi provider thành pass.

Để đánh giá chất lượng production, cần thêm corpus audio cuộc gọi thật đã được đồng ý sử dụng và
ground-truth do người Việt gán nhãn. Chỉ số tối thiểu:

- WER/CER trước và sau rewrite;
- entity error rate cho pickup/destination;
- độ chính xác số điện thoại, tiền, thời gian và mã chuyến;
- false-correction rate;
- confirmation/cancellation semantic flip rate bằng 0;
- p50/p95 latency và chi phí mỗi lượt.

## Rollout

1. Chạy live text quality gate bằng credential production hợp lệ.
2. Chạy corpus audio thật ở chế độ shadow: lưu metric/diff đã che PII, chưa đưa bản rewrite cho Agent.
3. Chỉ bật canary khi semantic flip rate bằng 0 và entity error giảm có ý nghĩa.
4. Theo dõi fallback reason, latency và cost; rollback bằng
   `VOICE_TRANSCRIPT_REWRITE_ENABLED=false`.

