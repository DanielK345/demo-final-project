# MUST DO — đầu vào bên ngoài bắt buộc

Cập nhật: **2026-08-16**.

File này chỉ chứa những việc không thể hoàn tất bằng code trong repository vì cần tài khoản,
credential, dữ liệu nghiệp vụ chính thức, hạ tầng vận hành hoặc phê duyệt của con người. Các lỗi
code, test, UI, schema và luồng Agent không được đẩy vào đây.

## 1. Chọn và cấp quyền cho Maps / geocoding / routing

Cần chủ dự án quyết định một nhà cung cấp production và cấp credential hợp lệ:

- Google Maps Platform, Mapbox, Goong hoặc VietMap; hoặc hạ tầng tự host Nominatim + OSRM.
- Xác nhận quyền lưu `place_id`, địa chỉ, tọa độ và polyline theo điều khoản của nhà cung cấp.
- Cấp API key theo từng môi trường, giới hạn domain/IP/quota và bật cảnh báo chi phí.
- Cung cấp polygon vùng phục vụ thật của AloSM.

Biến môi trường dự kiến (chỉ điền provider được chọn):

```env
MAPS_PROVIDER=
MAPS_API_KEY=
MAPS_BASE_URL=
MAPS_SERVICE_AREA_ID=
```

Tiêu chí nghiệm thu bên ngoài: tìm kiếm và reverse-geocode địa chỉ Việt Nam thật; route trả
`distance_meters`, `duration_seconds`, polyline; key bị giới hạn đúng môi trường; có quota alert.

## 2. Cung cấp dữ liệu nghiệp vụ AloSM đã phê duyệt

Business/Product/Ops phải cung cấp phiên bản có hiệu lực, owner và ngày hiệu lực cho:

- danh mục loại xe, sức chứa, hành lý và accessibility;
- bảng giá mở cửa, giá/km, giá/phút, phí chờ, phí hủy, giá tối thiểu và surge;
- voucher/promotion: điều kiện, ngân sách, phạm vi, stackability, thời hạn và thứ tự tối ưu;
- vùng phục vụ, fleet/driver availability và quy tắc dispatch;
- điều khoản dịch vụ, quyền riêng tư, ghi âm cuộc gọi, hoàn tiền, an toàn và khiếu nại;
- SLA/giờ hoạt động cho từng hàng đợi tổng đài.

Không được lấy giá/voucher của GreenSM/Grab/Be làm dữ liệu AloSM production nếu chưa có phê
duyệt bằng văn bản. Dữ liệu mẫu hiện tại chỉ dùng demo và được liệt kê trong
`src/agents/DATAFINDING.md`.

Tiêu chí nghiệm thu bên ngoài: mỗi dataset có `owner`, `version`, `effective_from`, cơ chế thu hồi
và một bộ case đối soát do business ký duyệt.

## 3. Hạ tầng dữ liệu production

Repository đã có SQLAlchemy/Alembic và migration cho handoff có cấu trúc. Để chạy production cần:

- tạo project Supabase/Postgres cho dev/staging/prod;
- cấp `DATABASE_URL` runtime và `DATABASE_URL_MIGRATIONS` qua secret manager;
- chạy migration tới revision mới nhất, cấu hình backup/PITR và kiểm tra restore;
- quyết định retention cho transcript, audio, vị trí, số điện thoại và audit events;
- cấp Redis/queue nếu triển khai nhiều instance hoặc worker bất đồng bộ.

```env
DATABASE_URL=
DATABASE_URL_MIGRATIONS=
REDIS_URL=
```

Tiêu chí nghiệm thu bên ngoài: restart/deploy nhiều instance không mất user/session/booking/
handoff; restore drill thành công; secrets không xuất hiện trong Git hoặc log.

## 4. Telephony, streaming voice và kênh chuyển người thật

Để “gọi điện” và transfer thật cần nhà cung cấp telephony/SIP và đích vận hành:

- mua/đăng ký số điện thoại hoặc SIP trunk;
- cấp webhook signing secret, credential gọi ra/vào và cấu hình recording consent;
- cung cấp queue/extension cho `SAFETY_OPERATOR`, `SPECIALIST_OPERATOR`,
  `CUSTOMER_CARE_OPERATOR`, `OPERATIONS_OPERATOR`, `GENERAL_OPERATOR`;
- xác nhận fallback khi không có tổng đài viên, timeout, ngoài giờ và cuộc gọi bị rớt;
- chọn STT/TTS production và cấp key/quota nếu không dùng provider local.

```env
TELEPHONY_PROVIDER=
TELEPHONY_ACCOUNT_ID=
TELEPHONY_SECRET=
TELEPHONY_FROM_NUMBER=
TELEPHONY_WEBHOOK_SECRET=
STT_PROVIDER=
STT_API_KEY=
TTS_PROVIDER=
TTS_API_KEY=
```

Tiêu chí nghiệm thu bên ngoài: cuộc gọi thật vào/ra, barge-in, reconnect, transfer có context,
không đọc PII nội bộ, đo được latency STT/Agent/TTS và ghi nhận consent.

## 5. OpenAI production access

Cần owner tài khoản OpenAI:

- cấp project/service-account key qua secret manager, không gửi key trong chat hoặc commit;
- xác nhận model ID được tài khoản cho phép và budget/rate limit;
- phê duyệt retention/data controls phù hợp dữ liệu khách hàng;
- tạo staging key tách khỏi production và cảnh báo chi phí.

```env
OPENAI_API_KEY=
AGENT_LLM_MODEL=gpt-5.6-luna
AGENT_LLM_ENABLED=true
```


Trạng thái kiểm tra thật ngày 2026-08-16: lời gọi `gpt-5.6-luna` qua Responses API đã chạy từ
pipeline mới nhưng OpenAI trả `AuthenticationError`. Owner cần thu hồi/thay key hiện tại, cấp key
staging hợp lệ và bảo đảm project có quyền với cả `gpt-5.6-luna` và `gpt-4o-transcribe`. Sau khi
cấp, bắt buộc chạy:

```powershell
.\.venv\Scripts\python.exe scripts/live_voice_rewrite_check.py
```

Gate phải pass thật; không thay lỗi credential/model/network bằng mock. Đồng thời cần phê duyệt
budget, rate limit và data control cho transcript rewrite (`store=false`, PII dạng số/email/ID đã
được mask; địa danh và phần ngôn ngữ còn lại vẫn được gửi để model có thể sửa chính tả).

Các biến production liên quan:

```env
VOICE_STT_MODEL=gpt-4o-transcribe
VOICE_TRANSCRIPT_REWRITE_ENABLED=true
VOICE_TRANSCRIPT_REWRITE_MODEL=gpt-5.6-luna
VOICE_TRANSCRIPT_REWRITE_TIMEOUT_SECONDS=5
VOICE_TRANSCRIPT_REWRITE_REASONING_EFFORT=none
VOICE_TRANSCRIPT_REWRITE_MINIMUM_CONFIDENCE=0.85
```
Tên model phải được kiểm tra lại trên tài liệu OpenAI chính thức tại thời điểm deploy; không suy ra
quyền truy cập chỉ vì model xuất hiện trong catalog.

## 6. Payment và notification thật

Chỉ triển khai giao dịch/hoàn tiền/gửi SMS-email production sau khi có:

- merchant sandbox + production của VNPay/MoMo/Stripe hoặc provider được chọn;
- webhook secret, callback domain, chính sách reconciliation/refund;
- tài khoản SMS/email, sender đã xác minh và template được duyệt.

```env
PAYMENT_PROVIDER=
PAYMENT_MERCHANT_ID=
PAYMENT_SECRET=
PAYMENT_WEBHOOK_SECRET=
SMS_PROVIDER_API_KEY=
SMTP_HOST=
SMTP_USER=
SMTP_PASSWORD=
```

Tiêu chí nghiệm thu bên ngoài: webhook được xác minh chữ ký và idempotent; sandbox reconciliation
pass; notification có opt-in/opt-out và không rò PII.

## 7. Phê duyệt an toàn, pháp lý và vận hành

Con người có thẩm quyền phải phê duyệt:

- playbook tai nạn, đe dọa, quấy rối, tài xế say và số khẩn cấp theo khu vực;
- nội dung bot được phép nói, đặc biệt không hứa bồi thường/hoàn tiền hay kết luận trách nhiệm;
- consent ghi âm, retention, quyền xóa/truy xuất dữ liệu và phân quyền operator;
- pentest, load test, disaster recovery và go-live checklist;
- bộ transcript đã ẩn danh dùng làm eval, gồm giọng vùng miền và lỗi ASR thực tế.
- cung cấp ít nhất một fixture PCM16 mono 16 kHz có giọng nói thật, consent và ground-truth; cấu hình `VOICE_LIVE_PCM16_FIXTURE` để chạy full WebSocket integration test.

Tiêu chí nghiệm thu bên ngoài: có người chịu trách nhiệm, ngày phê duyệt, SLA và diễn tập handoff
khẩn cấp trước go-live.