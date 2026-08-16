# Transcript rewrite contract

Cập nhật: **2026-08-16** · Trạng thái: `CURRENT`.

## Mục tiêu

LLM rewrite chỉ sửa lỗi chính tả/tách từ/thiếu dấu khi bằng chứng đã có trong
transcript. Nó không nghe lại audio, không tạo business fact và không được thay đổi
confirmation, cancellation, phủ định, số tiền, thời gian, mã hoặc địa chỉ.

```text
ASR transcript
  -> gazetteer + deterministic normalization
  -> immutable PII placeholders
  -> OpenAI-compatible Structured Output
  -> deterministic semantic/placeholder guard
  -> restore PII in process
  -> accept rewrite hoặc giữ nguyên transcript
```

## Runtime

- Implementation: `src/backend/services/transcript_rewriter.py`.
- Tích hợp tại cả `/api/v1/voice/turn` và `/api/v1/voice/stream`.
- Không gửi conversation history; context chỉ gồm workflow/step cần thiết.
- Request đặt `store=false`; session identifier được hash.
- Email, số, điện thoại, thời gian và mã chữ-số được mask thành placeholder.
- Model mặc định hiện hành lấy từ `VOICE_TRANSCRIPT_REWRITE_MODEL`.
- Timeout/failure/schema error/semantic doubt đều fallback về transcript trước rewrite.

## Acceptance rules

Rewrite bị từ chối khi:

- placeholder bị thêm, xóa, đổi hoặc đảo thứ tự;
- model báo không bảo toàn nghĩa hoặc cần clarification;
- confirmation/cancellation/negation thay đổi;
- similarity, confidence hoặc token-delta vi phạm guard;
- output rỗng, sai schema hoặc provider timeout/error.

Không nâng STT confidence dựa trên LLM rewrite.

## Live gate

```powershell
.\.venv\Scripts\python.exe scripts\live_voice_rewrite_check.py
```

Script gọi provider thật và phải fail khi auth/model/schema/PII/semantic gate lỗi.
Unit test hoặc fake model không thay live acceptance.

Production release cần corpus cuộc gọi đã consent/ẩn danh và ground truth người Việt,
đo WER/CER, entity error, false-correction, semantic-flip, latency và cost theo accent/
noise/provider. Gate confirmation/cancellation/negation semantic flip phải bằng 0.

Rollback: `VOICE_TRANSCRIPT_REWRITE_ENABLED=false`.
