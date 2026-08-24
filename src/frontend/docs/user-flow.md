# AloSM user flow

Cập nhật: **2026-08-16**.

## 1. Đăng nhập và khởi tạo phiên

1. Người dùng vào `/login`, đăng nhập hoặc đăng ký.
2. Nếu tài khoản bật TOTP, UI yêu cầu mã 6 số trước khi cấp access token.
3. Sau đăng nhập, `AppLayout` hiển thị Sidebar/Topbar/MobileNav và nút gọi AloSM Voice.
4. `VoiceAssistantProvider` khôi phục session hợp lệ hoặc tạo `POST /api/v1/sessions`.

## 2. Điều hướng chính

- `/`: tổng quan, dịch vụ, chuyến gần đây và CTA mở trợ lý.
- `/booking`: danh mục dịch vụ và điểm bắt đầu đặt xe.
- `/tracking`: theo dõi booking hiện tại qua API trạng thái chuyến.
- `/activity`: lịch sử booking từ backend.
- `/payment`: cài đặt, mật khẩu và TOTP; payment gateway thật chưa được cấp.
- `/profile`: hồ sơ người dùng.

CTA chỉ mở Voice popup và điền **bản nháp có thể sửa**. CTA không tự gửi câu lệnh thành lời
của người dùng. Người dùng phải bấm gửi hoặc nói trực tiếp.

## 3. Đặt xe bằng Voice AI

```text
CTA hoặc nút Voice
  -> popup cuộc gọi
  -> nói / sửa và gửi bản nháp
  -> pickup + destination
  -> Backend search/resolve candidate
  -> chọn loại xe phù hợp
  -> Backend lấy quote
  -> Agent đọc tóm tắt
  -> modal CONFIRM
  -> explicit confirmation
  -> create_booking idempotent
  -> success / tracking
```

Quy tắc an toàn:

- greeting/bare intent/garbage không trở thành địa chỉ;
- địa chỉ chưa resolve vẫn là missing;
- thay pickup/destination/vehicle làm mất hiệu lực quote và confirmation cũ;
- frontend không gọi create-booking trực tiếp;
- chỉ `CONFIRM` rõ ràng mới tạo side effect;
- duplicate tool result không tạo booking lần hai.

## 4. Bản đồ, xe và voucher trong popup

Popup có ba tab Bản đồ/Loại xe/Ưu đãi để follow UI mẫu. Ở trạng thái hiện tại:

- pickup/destination và quote thật đến từ `booking_progress` của backend;
- bản đồ nền, marker xe gần, ETA catalog và voucher đang là **minh họa**, được ghi nhãn rõ;
- voucher chưa được gửi vào booking vì chưa có Promotion API/business rules;
- không click vào vị trí mặc định để biến “vị trí hiện tại” hoặc một địa danh hard-code thành địa chỉ.

Khi có provider thật, UI phải lấy place/route/fleet/promotion từ API và giữ nguyên bước confirmation.

## 5. Điều khiển bằng giọng nói

- VAD tự thu một utterance khi micro bật.
- Backend trả transcript cuối turn, không phải caption streaming từng chữ.
- Câu trả lời được đọc qua audio provider hoặc browser TTS fallback.
- Người dùng có thể nói mở bản đồ/chọn xe/voucher hời nhất để đổi tab; mọi lựa chọn tạo booking vẫn
  phải đi qua Agent/Backend và confirmation.
- Tắt loa không tắt micro; tắt micro không kết thúc session.

## 6. Human handoff

Handoff có thể xảy ra khi emergency/safety risk, complaint, payment dispute, lost item, repeated low
STT confidence, model/tool failure, side-effect reconciliation hoặc yêu cầu người thật.

Agent tạo context đã redacted gồm `reason_code`, priority, severity, queue, summary và pending tool.
Backend lưu case `pending`; operator nhận case qua API rồi accept. Telephony transfer thật chỉ hoạt
động sau khi cấu hình SIP/provider và operator queues trong `mustdo.md`.

## 7. Kết thúc, resume và lịch sử

- Đóng popup chỉ ẩn UI, không tự kết thúc session.
- “Kết thúc” gọi endpoint end-session; “Gọi lại” tạo session mới.
- Lịch sử/transcript đọc từ backend log và chỉ cho user sở hữu session.
- Booking thành công mới cho gửi rating.