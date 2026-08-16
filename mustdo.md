# MUST DO — đầu vào bên ngoài bắt buộc

Cập nhật: **2026-08-16**.

File này chỉ chứa những việc không thể hoàn tất bằng code trong repository vì cần tài khoản,
credential, dữ liệu nghiệp vụ chính thức, hạ tầng vận hành hoặc phê duyệt của con người. Các lỗi
code, test, UI, schema và luồng Agent không được đẩy vào đây.

Nguồn điều phối: `docs/PROJECT_SOURCE_OF_TRUTH.md`. Để tránh làm sai dependency, owner nên đóng
các nhóm theo thứ tự: **(1)** xoay secret + chọn owner/pháp lý, **(2)** production DB,
**(3)** Maps và dữ liệu business, **(4)** booking/dispatch, **(5)** telephony/handoff,
**(6)** ASR/TTS release gates, **(7)** payment/notification, **(8)** security/load/DR/go-live.
Một mục chỉ được đóng khi có artifact verify, ngày chạy và người chịu trách nhiệm; có credential
không đồng nghĩa tích hợp đã sẵn sàng production.

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

## 3. Hạ tầng dữ liệu production cần owner/hạ tầng

Kết nối Supabase/Postgres và Alembic đã được kiểm tra thật ngày 2026-08-16: `current` khớp
`0002_handoff_operations (head)` và SQLAlchemy thực hiện được query. Không cần tạo lại project chỉ để
chứng minh database hoạt động.

Phần còn cần con người/hạ tầng:

- tạo/tách project hoặc schema dev, staging và prod theo chính sách tổ chức;
- đưa `DATABASE_URL` và `DATABASE_URL_MIGRATIONS` vào secret manager, xoay password theo lịch;
- chọn/cấp Redis nếu cần distributed lock, rate limit hoặc worker coordination;
- chọn Supabase plan, cấu hình backup/PITR và thực hiện restore drill thật;
- phê duyệt retention/xóa/export cho transcript, audio, vị trí, phone hash và audit event;
- chỉ bật Supabase Data API cho bảng cần thiết; cấp explicit grant và ownership RLS đã review.

```env
DATABASE_URL=
DATABASE_URL_MIGRATIONS=
REDIS_URL=
```

Expected artifact: inventory môi trường, secret references, backup/PITR policy, restore report, retention
approval và Redis decision. Verify bằng restore vào môi trường cô lập, Alembic revision, FK integrity,
row counts và multi-instance test. Việc wire repository trong code không thuộc `mustdo.md` và không
được chuyển sang đây.
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

## 5. LLM/OpenRouter production access

Pipeline LLM hiện dùng OpenRouter qua giao thức OpenAI-compatible, tách credential khỏi OpenAI Speech:

```env
OPENROUTER_API_KEY=
AGENT_LLM_MODEL=openai/gpt-5.6-luna-pro
AGENT_LLM_BASE_URL=https://openrouter.ai/api/v1
AGENT_LLM_ENABLED=true
VOICE_TRANSCRIPT_REWRITE_MODEL=openai/gpt-5.6-luna-pro
VOICE_TRANSCRIPT_REWRITE_BASE_URL=https://openrouter.ai/api/v1
```

Trạng thái kiểm tra thật ngày 2026-08-16: credential OpenRouter hoạt động, model catalog xác nhận
`openai/gpt-5.6-luna-pro` hỗ trợ Structured Outputs, và `scripts/live_voice_rewrite_check.py`
đã pass 5/5 case thật. Request được giới hạn output token để tránh OpenRouter từ chối `402` do dự
trù output tối đa.

Việc owner vẫn phải làm:

- Thu hồi và tạo lại OpenRouter key đã từng được gửi trong hội thoại; cập nhật key mới chỉ qua secret
  manager hoặc `.env` cục bộ, không commit.
- Cấp budget/rate limit và cảnh báo chi phí cho staging/production.
- Phê duyệt retention/data controls cho transcript. Pipeline đặt `store=false`, mask số/email/ID và
  không gửi lịch sử hội thoại; phần ngôn ngữ và địa danh còn lại vẫn phải gửi để sửa lỗi STT.
- Duy trì credential riêng cho Speech-to-Text/Text-to-Speech. `OPENROUTER_API_KEY` không được dùng
  thay `OPENAI_API_KEY`; WebSocket ASR có thể dùng `GROQ_API_KEY`.
- Cấp OpenAI Speech key hợp lệ nếu dùng `/voice/turn` với `gpt-4o-transcribe`, hoặc cấu hình speech
  provider production khác đã được phê duyệt.

Sau khi xoay key, bắt buộc chạy lại gate thật:

```powershell
.\.venv\Scripts\python.exe scripts/live_voice_rewrite_check.py
```

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
## 8. ZipFormer ASR — việc bắt buộc cần con người/hạ tầng

### 8.1 Phê duyệt giấy phép trước commercial production

1. **Việc làm:** Legal/Product owner xác nhận quyền dùng `hynt/Zipformer-30M-RNNT-6000h` hoặc chọn model thay thế.
2. **Tại sao:** model card hiện ghi `CC-BY-NC-ND-4.0`, không được tự coi là phù hợp dịch vụ thương mại.
3. **Ở đâu:** hồ sơ third-party software/model và quyết định go-live của dự án.
4. **Thao tác:** lưu văn bản phê duyệt cùng model ID, revision và phạm vi sử dụng; nếu không được duyệt, thay artifact/config rồi chạy lại toàn bộ gate ASR.
5. **Expected:** có owner, ngày phê duyệt và bằng chứng quyền sử dụng.
6. **Verify:** audit release artifact khớp model/revision/license đã duyệt.
7. **Risk:** vi phạm giấy phép và phải dừng dịch vụ.

### 8.2 Xác minh Docker bằng daemon có quyền hoạt động

1. **Việc làm:** build và chạy container thật trên máy có Docker daemon.
2. **Tại sao:** máy hiện tại có Docker CLI nhưng `com.docker.service` dừng; tài khoản phiên này không có quyền start service, nên chưa thể trung thực đánh dấu Docker build/run pass.
3. **Ở đâu:** Docker Desktop hoặc CI runner của dự án.
4. **Command:** `docker build -t alosm-zipformer .`; sau đó `docker run --rm -p 8000:8000 --env-file .env alosm-zipformer`.
5. **Expected:** build tải artifact đúng SHA-256; container chạy non-root; `/health/ready` trả 200 và upload WAV trả transcript thật.
6. **Verify:** `curl.exe http://localhost:8000/health/ready` và lệnh upload trong `docs/voice-ai/zipformer-asr.md`.
7. **Risk:** lỗi package/platform hoặc model path chỉ xuất hiện khi deploy.

### 8.3 Nghiệm thu trên audio cuộc gọi và phần cứng production

1. **Việc làm:** cung cấp corpus cuộc gọi tiếng Việt đã consent/ẩn danh và CPU/RAM mục tiêu; đo WER/CER theo miền, vùng giọng, nhiễu và tải dài hạn.
2. **Tại sao:** WAV đi kèm model chứng minh pipeline chạy thật nhưng không đại diện điện thoại 8 kHz, tiếng ồn, địa chỉ/POI và giọng vùng miền của khách hàng.
3. **Ở đâu:** môi trường staging với telephony codec thật và dashboard metrics.
4. **Command:** chạy `scripts/benchmark_zipformer.py` trên SKU production; bổ sung evaluator WER/CER sau khi corpus được cấp hợp pháp.
5. **Expected:** SLO latency/error/memory, WER/CER và tuning worker/thread được owner ký duyệt.
6. **Verify:** soak test không tăng RSS không kiểm soát, error rate <1%, RTF theo gate và báo cáo slice chất lượng.
7. **Risk:** transcript địa chỉ sai, handoff sai, quá tải RAM/CPU hoặc chất lượng giảm ngoài tập mẫu.
## 9. TTS output — kiểm duyệt bắt buộc còn cần con người/hạ tầng

### 9.1 Human listening review tiếng Việt

1. **Việc làm:** ít nhất hai reviewer tiếng Việt nghe corpus trong `scripts/live_tts_output_check.py` và bộ câu nghiệp vụ đã consent; chấm HoaiMy/NamMinh về tự nhiên, rõ, nhịp nghỉ, địa chỉ, số tiền, phủ định và persona thương hiệu.
2. **Tại sao:** TTS→ZipFormer, CER/WER và audio metrics không thay thế khả năng nghe cảm nhận bằng tai người.
3. **Ở đâu:** staging Voice UI trên Chrome/Edge và thiết bị/loa/tai nghe đại diện người dùng.
4. **Thao tác:** chạy `scripts/live_tts_output_check.py`, mở audio qua chính `/api/v1/voice/speak`; ghi `case_id`, reviewer, voice, điểm, lỗi và quyết định.
5. **Expected:** hai reviewer ký duyệt, không có lỗi đổi nghĩa/phủ định/giá/địa chỉ và có voice/persona được Product phê duyệt.
6. **Verify:** biên bản review gắn model/provider version và ngày chạy; case fail có regression fixture sau khi được phép lưu.
7. **Risk:** audio đạt chỉ số kỹ thuật nhưng vẫn nghe máy, sai nhịp hoặc phát âm thương hiệu không phù hợp.

### 9.2 Provider TTS có SLA cho production

1. **Việc làm:** Platform/Procurement chọn và cấp credential cho provider Speech chính thức có SLA, quota, DPA và quyền thương mại; giữ Edge-TTS làm fallback/dev nếu policy cho phép.
2. **Tại sao:** Edge-TTS là online best-effort và live audit đã quan sát `NoAudioReceived`/timeout theo câu ở cả HoaiMy lẫn NamMinh.
3. **Ở đâu:** secret manager, billing account và hồ sơ third-party vendor của production.
4. **Thao tác:** tích hợp provider qua contract `TTSProvider`, không bypass `TTSOrchestrator`; chạy lại cùng live report, load/soak và failover drill.
5. **Expected:** SLO, quota/cost alert, retry policy và data retention được phê duyệt.
6. **Verify:** canary thực tế, dashboard error/fallback/p95 và diễn tập provider outage.
7. **Risk:** cả hai Edge voice cùng lỗi khiến TTS trả 503 dù backend/ASR/Agent còn khỏe.

### 9.3 Device/browser playback matrix

1. **Việc làm:** QA kiểm tra autoplay, mute/unmute, Bluetooth, đổi output device, background tab và cuộc gọi liên tiếp trên browser/mobile mục tiêu.
2. **Tại sao:** AI agent không thể tự cấp quyền media hoặc xác nhận âm thanh phát qua thiết bị vật lý của người dùng.
3. **Ở đâu:** staging HTTPS trên Chrome/Edge và thiết bị nằm trong support matrix.
4. **Expected:** không nói đè, không Promise treo, lỗi phát được hiển thị và audio dừng khi mute/unmount.
5. **Verify:** test record có browser/version/device và video/log network-console.
6. **Risk:** server audio đúng nhưng người dùng nghe im lặng hoặc audio cũ phát đè lượt mới.