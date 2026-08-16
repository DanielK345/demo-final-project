# Kế hoạch tích hợp Điều khoản và Chính sách AloSM

Cập nhật: **2026-08-16** · Policy version: **2026-08-16** · Owner approval: **PROJECT_OWNER_SELF_REVIEW**

## Nguyên tắc

- Bản nguồn do chủ dự án cung cấp được giữ nguyên byte, SHA-256 và attribution; không âm thầm đổi
  Green SM/GSM thành AloSM.
- Runtime chỉ dùng operational rules đã được chủ dự án phê duyệt, có citation/version/effective time.
- Thông tin pháp nhân, hotline, email và địa chỉ Green SM/GSM không phải thông tin AloSM.
- Consent đăng ký, cookie không thiết yếu và giọng nói là ba lựa chọn riêng.
- Agent không tự hứa hoàn tiền/bồi thường, không tự áp phí và không trả lời policy từ trí nhớ model.

## Trình tự triển khai

1. **Canonical source:** lưu bản nguồn immutable, manifest typed, checksum fail-closed và document index.
2. **Backend:** PolicyService, public API current/source, policy version validation khi đăng ký và
   acceptance audit trong user record.
3. **RAG:** thay FAQ hard-code bằng approved operational rules; trả citation, version, effective time,
   source hash và legal notice.
4. **Agent LLM:** buộc retrieve trước câu hỏi policy; guard pháp nhân; privacy/legal/refund escalation;
   giá/phí thay đổi phải được backend xác nhận.
5. **Frontend:** trang policy công khai, tìm kiếm rule, xem toàn bộ nguồn, checkbox đăng ký, cookie
   choice, voice consent trước `getUserMedia`, tùy chọn chat chữ và policy version trong Profile.
6. **Tests:** checksum/tamper, API/source consistency, stale acceptance, RAG citation, identity guard,
   consent-gated microphone, Agent handoff và full regression.
7. **Governance:** cập nhật `data/catalog.json`, `DATAFINDING.md`, source of truth và `mustdo.md`.

## Contract chính

- `GET /api/v1/policies/current`: metadata, document index và operational rules.
- `GET /api/v1/policies/current/source`: bản nguồn nguyên vẹn cùng SHA-256 và legal notice.
- `POST /api/v1/auth/register`: bắt buộc `accepted_terms_version` và
  `accepted_privacy_version` khớp catalog hiện hành.
- `GET /api/v1/auth/me`: trả policy acceptance version/time nếu đã ghi nhận.

## Gate production còn lại

- Pháp nhân, hotline, email support/DPO và địa chỉ AloSM được xác minh.
- Acceptance/withdrawal/export/delete được lưu bền vững trong Postgres, có audit và retention.
- Bộ eval policy thật pass groundedness, citation correctness, stale-policy và prompt injection.
- Policy rollback/canary, thông báo trước 07 ngày và operator queue privacy/legal hoạt động thật.
