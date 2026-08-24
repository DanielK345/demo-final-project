# AloSM Voice AI — MVP scope và acceptance

Cập nhật: **2026-08-16** · Phân loại: `PRODUCT` · Đồng bộ PRD v1.2.

Tài liệu này định nghĩa phạm vi và điều kiện nghiệm thu MVP. Trạng thái code thực tế nằm tại
[PROJECT_SOURCE_OF_TRUTH.md](PROJECT_SOURCE_OF_TRUTH.md); yêu cầu đầy đủ nằm tại
[PRD_AloSM_Voice.md](PRD_AloSM_Voice.md).

## 1. Mục tiêu

Chứng minh một kênh trợ lý giọng nói/text an toàn cho hành trình dịch vụ AloSM:

```text
Khách nói/nhập yêu cầu
  → ASR và kiểm duyệt transcript
  → Agent thu thập, resolve và kiểm chứng dữ liệu
  → đọc/tóm tắt lựa chọn + xác nhận rõ ràng
  → thực thi công cụ nghiệp vụ hoặc handoff
  → kiểm duyệt output + TTS/UI
```

## 2. Must-have của MVP

### F1 — Đặt xe bằng giọng nói/text

- Thu thập điểm đón, điểm đến, loại xe và lựa chọn liên quan theo hội thoại nhiều lượt.
- Không biến địa chỉ free-form thành địa điểm đã resolve khi chưa có provider/candidate.
- Giá, ETA, xe và voucher chỉ đến từ Backend/provider có provenance và thời hạn.
- Đọc summary trước khi xác nhận; tạo booking bắt buộc có explicit confirmation.
- Thay đổi location/vehicle làm quote và confirmation cũ mất hiệu lực.
- Dùng idempotency; chỉ nói “đặt xe thành công” sau kết quả Backend đã xác nhận.

### F2 — Human handoff có context

Handoff khi người dùng yêu cầu, có emergency/safety, khiếu nại cần phán đoán, nhiều lần
low-confidence, lỗi công cụ/model nghiêm trọng hoặc side effect có kết quả không xác định.
Context phải redacted và có reason, priority, severity, queue, pending action cùng correlation IDs.
Web MVP có thể chứng minh lifecycle; telephony transfer thật là release gate bên ngoài.

### F3 — Thông tin, FAQ và tra cứu chuyến

- Chỉ trả lời từ nguồn đủ tin cậy, còn hiệu lực và có provenance.
- Tra cứu theo identifier đã validate và ownership; multi-match phải hỏi người dùng chọn.
- Không bịa trip, driver, ETA, chính sách hay cam kết hoàn tiền.
- Không đủ căn cứ thì nói chưa xác thực hoặc handoff.

### F9 — An toàn và khẩn cấp

- Nhận diện tín hiệu tai nạn, đe dọa, mất an toàn hoặc cần trợ giúp khẩn.
- Không tiếp tục luồng bán hàng/booking khi ưu tiên an toàn đã kích hoạt.
- Nêu rõ giới hạn của AI, hướng dẫn hành động an toàn phù hợp và tạo handoff ưu tiên cao.
- Không tuyên bố đã gọi cơ quan khẩn cấp hay đã kết nối người thật khi chưa có bằng chứng.

## 3. Should-have theo PRD v1.2

- **F4 — Identity, consent và access control:** xác thực, ownership, consent, RBAC và audit.
- **F5 — Knowledge và quality:** corpus được phê duyệt/version hóa, đánh giá groundedness và chất lượng hội thoại.
- **F6 — Payment:** provider thật, confirmation, webhook, idempotency và reconciliation; không đọc dữ liệu nhạy cảm.
- **F7 — Refund/complaint:** phân loại, thu thập bằng chứng tối thiểu, tạo case và handoff khi cần phán đoán.
- **F8 — Driver support:** xác thực tài xế, thao tác rảnh tay an toàn và không khuyến khích dùng màn hình khi lái xe.

Các mục F4–F8 chỉ được công bố ở mức runtime tương ứng trong Source of Truth; phần thiếu provider,
credential, consent hoặc phê duyệt nghiệp vụ phải nằm trong `mustdo.md`.

## 4. Frontend MVP

- Đăng nhập/đăng ký, auth guard và ownership nhất quán.
- Voice assistant popup hoạt động trên các route chính; typed fallback minh bạch.
- Hiển thị transcript/reply, trạng thái booking, candidate, vehicle, quote, voucher và confirmation.
- Không nuốt playback error và không âm thầm đổi sang browser voice.
- Activity/tracking đọc từ Backend; map/fleet/voucher/payment demo phải gắn nhãn rõ.

## 5. Voice MVP

- Validate loại, kích thước, duration và khả năng decode audio.
- ASR thật hoặc typed unavailable error; không tạo transcript giả.
- Transcript rewrite bảo toàn PII placeholder, số, địa chỉ, tên riêng, phủ định và confirmation.
- Output review chặn PII/internal data, booking chưa xác nhận và cam kết không có căn cứ.
- TTS có timeout, fallback hữu hạn, audio validator và không trả audio rỗng.
- Low-confidence, safety và handoff có regression test.

## 6. Backend và data MVP

- Typed request/response, Agent state và tool lifecycle rõ ràng.
- Session, booking và handoff có ownership, idempotency và correlation.
- Migration/schema tồn tại cho persistent entities; process-memory chỉ được coi là demo/local.
- Health/readiness, structured logs và redaction hoạt động.
- Maps, fleet, dispatch, pricing, promotion, payment và policy production không được giả lập thành sự thật.

## 7. Acceptance scenarios

1. Booking happy path resolve location → quote → summary → confirmation → đúng một booking.
2. Sửa pickup/destination/vehicle làm quote và confirmation cũ không còn dùng được.
3. Confirmation mơ hồ hoặc low-confidence không tạo booking.
4. Duplicate/replayed tool result không tạo side effect lần hai.
5. Trip/FAQ single-match, multi-match, no-match không bịa dữ liệu.
6. Emergency, complaint, explicit human request và provider failure tạo handoff đúng ưu tiên.
7. ASR/TTS/provider unavailable trả lỗi hoặc fallback minh bạch.
8. PII, secret và nội dung nội bộ không bị đọc hoặc ghi ra log công khai.
9. Payment/refund/driver flow chưa có provider thật không được công bố là hoàn thiện.

## 8. Definition of Done

- Backend/Agent/Voice tests, Ruff và compile pass.
- Frontend lint, typecheck và build pass.
- OpenAPI/schema/frontend types khớp.
- Live-provider gate chạy riêng; mock/fake không được dùng làm acceptance evidence.
- Không có secret trong Git hoặc log công khai.
- Mọi dữ liệu demo có nhãn; mọi production claim tuân taxonomy trong Source of Truth.
- External blocker được ghi duy nhất tại `mustdo.md` với owner, evidence và cách verify.

## 9. Ngoài MVP/release-gated

- telephony/SIP transfer production;
- maps/fleet/dispatch/pricing/promotion/payment production;
- vận hành multi-region/high-scale;
- commercial go-live trước license, privacy, security, load, DR và human-listening sign-off.
