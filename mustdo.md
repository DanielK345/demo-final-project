# MUST DO — thao tác owner/hạ tầng còn lại

Cập nhật **2026-08-20** cho migration head `0005_livekit_voice_state` (revises: `0004_maps_places_routes`). Phần persistence, repository, quote integrity, snapshot, LiveKit voice agent, ASR modules, observability và test coverage đã được AI triển khai qua merge 3 nhánh (feature/agentic-ai + feature/backend-data → feature/voice-ai). Những mục dưới đây cần quyền thay đổi database live, tài khoản hạ tầng hoặc phê duyệt nghiệp vụ; không thể hợp lệ hóa chỉ bằng code.

## P0.1 — Phê duyệt và áp dụng migration PostgreSQL live

**Tại sao bạn phải làm:** database Supabase live đang ở `0002_handoff_operations` hoặc `0004_maps_places_routes`; migration mới nhất sau merge ngày 2026-08-20 là `acc88dbc1e83` (merge: `0005_livekit_voice_state` + `fc877ccd583a_link_fare_quotes_to_route_snapshots`). Thao tác đổi schema là mutation bền vững — cần phê duyệt live rõ ràng.

**Migrations mới so với 2026-08-16:**
- `0005_livekit_voice_state` — thêm cột `voice_agent_state` (JSONB) và `voice_state_revision` (BigInteger) vào bảng `ride_sessions`
- `fc877ccd583a` — thêm cột `route_snapshot_id` FK vào bảng `fare_quotes`
- `acc88dbc1e83` — merge migration (không có DDL, chỉ hợp nhất 2 heads)

1. Mở Supabase Dashboard → project đúng môi trường → **Database → Backups**.
2. Xác nhận có backup gần nhất hoặc PITR; ghi lại timestamp và người chịu trách nhiệm.
3. Thông báo maintenance window; tạm dừng deploy/worker đang ghi DB.
4. Trong terminal tại root project, kiểm tra đúng branch và revision:

   ```powershell
   git branch --show-current
   uv run python -m alembic heads
   uv run python -m alembic current
   ```

   Expected: branch `feature/voice-ai`, head `acc88dbc1e83 (head)`, current là revision hiện tại.
5. Cấp phê duyệt rõ ràng cho mutation database live, sau đó chạy:

   ```powershell
   uv run python -m alembic upgrade head
   uv run python -m alembic current
   uv run python -m alembic check
   ```

6. Expected: current `acc88dbc1e83 (head)`; check báo `No new upgrade operations detected`.
7. Nếu lỗi: dừng ngay; không `stamp head`, không sửa tay schema. Lưu lỗi/revision và restore theo runbook nếu migration đã commit một phần.

**Bằng chứng đóng mục:** backup/PITR timestamp, output current/check, người phê duyệt, môi trường và thời gian thực hiện.

## P0.1 — Chạy migration head lên PostgreSQL thật (ĐÃ HOÀN THÀNH ✅)

- **Trạng thái**: Đã chạy thành công `uv run alembic upgrade head` lên database Supabase (`db.bmnnykrmesauqaikbcot.supabase.co`).
- **Revision hiện tại**: `acc88dbc1e83 (head) (mergepoint)`.
- **Schema đã tạo đầy đủ**: Users, Auth tokens, User settings, Ride sessions, Conversation messages/events, Bookings, Trips, Handoffs, Calls, Places, Route snapshots, Pricing catalog versions, Fare quotes, Idempotency records, Outbox events.

## P0.2 — Chạy acceptance PostgreSQL thật (ĐÃ HOÀN THÀNH ✅)

- **Trạng thái**: Script `scripts/verify_postgres_persistence.py` đã chạy trực tiếp trên Supabase PostgreSQL và pass 100% không mock:
  - `POSTGRES_PERSISTENCE_ACCEPTANCE=PASS`
  - `ALEMBIC_REVISION=acc88dbc1e83`
  - `QUOTE_TAMPER_REJECTION=PASS`
  - `CONCURRENT_IDEMPOTENCY=PASS`
  - `RESTART_READBACK=PASS`
  - `RLS_ENABLED=PASS`


## P0.3 — Tách runtime role least-privilege khỏi migration owner

1. Trong Supabase SQL Editor hoặc quy trình DBA, tạo login role riêng cho app runtime; không dùng `postgres`/owner và không cấp `BYPASSRLS`, `CREATEDB`, `CREATEROLE`.
2. Cấp `CONNECT`, `USAGE` schema và đúng quyền `SELECT/INSERT/UPDATE` cần thiết cho các bảng runtime; cấp sequence usage cho bảng autoincrement. Không cấp `ALTER`, `DROP`, `CREATE`.
3. Giữ `DATABASE_URL_MIGRATIONS` ở secret riêng chỉ CI migration/DBA truy cập. Đổi `DATABASE_URL` sang runtime role qua Supavisor transaction pooler.
4. Restart canary và chạy health/login/session/quote/booking/cancel/handoff.
5. Xác minh:

   ```sql
   SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls
   FROM pg_roles WHERE rolname = '<runtime_role>';
   ```

   Tất cả cờ đặc quyền phải `false`.
6. Supabase Dashboard → **Database → Advisors → Security** và **Performance**; xử lý toàn bộ finding P0/P1, đặc biệt RLS, exposed tables, missing FK index và duplicate index.

**Lưu ý auth:** dự án dùng custom auth qua backend, không được tạo policy giả dựa trên `auth.uid()`. Nếu muốn dùng Supabase Data API/Auth về sau, phải thiết kế tenant/owner policies riêng và có security review.

## P0.4 — Backup, restore, retention và secret rotation

1. Chọn retention cho account/token, session/transcript, location, quote/booking, call/handoff và audit/outbox; có Legal/Privacy approval.
2. Tạo backup theo lịch và cảnh báo backup failure.
3. Restore backup vào project/database cô lập, chạy Alembic current, FK/orphan checks, row counts và smoke API; ghi RTO/RPO thực tế.
4. Đưa `DATABASE_URL`, `DATABASE_URL_MIGRATIONS`, `QUOTE_SIGNING_KEY`, `FIELD_ENCRYPTION_KEY` vào secret manager; xóa bản rò rỉ khỏi kênh chat/log và rotate credential đã từng chia sẻ.
5. Rotate quote key chỉ sau khi quote dùng key cũ hết TTL hoặc đã có key ring/version.
6. Rotate field encryption key bằng batch decrypt-old/encrypt-new có checkpoint/rollback; không thay thẳng vì TOTP ciphertext cũ sẽ không giải mã được.

**Bằng chứng đóng mục:** restore report, RTO/RPO, retention matrix, secret references (không phải secret value), rotation/canary report.

## P0.5 — Dữ liệu nghiệp vụ để quote trở thành production

Code hiện cố ý lưu nhãn `DEMO`. Finance/Product/Ops phải cung cấp và ký duyệt:

1. vehicle catalog thật (capacity, luggage, accessibility);
2. bảng giá theo region/version/effective date, minimum fare, tier/km/time/wait/cancel/no-show, surcharge và rounding;
3. Maps/Route provider, service area và quyền lưu place/coordinate/polyline;
4. voucher eligibility, budget, stackability, ranking và version;
5. Fleet/Dispatch API, timeout/unknown-outcome reconciliation và SLA;
6. golden cases có input route/time/vehicle/voucher và expected breakdown/tổng tiền.

Sau khi nhận artifact: tạo **version mới** trạng thái `APPROVED`, không sửa catalog DEMO tại chỗ; chạy đối soát golden cases qua quote API và booking snapshot; Finance/Product ký kết quả.

**Bằng chứng đóng mục:** source checksum, owner/approver, effective period, rollback version, golden-case report và provider credentials trong secret manager.

---
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
- pháp nhân, hotline, email, địa chỉ liên hệ AloSM; retention/xóa/export và đầu mối xử lý quyền dữ liệu;
- SLA/giờ hoạt động cho từng hàng đợi tổng đài.

Không được lấy giá/voucher của GreenSM/Grab/Be làm dữ liệu AloSM production nếu chưa có phê
duyệt bằng văn bản. Dữ liệu mẫu hiện tại chỉ dùng demo và được liệt kê trong
`src/agents/DATAFINDING.md`.

Tiêu chí nghiệm thu bên ngoài: mỗi dataset có `owner`, `version`, `effective_from`, cơ chế thu hồi
và một bộ case đối soát do business ký duyệt.

### 2.1 Phê duyệt catalog giá DEMO được nhập ngày 2026-08-16

Catalog `data/pricing/hanoi_demo_2026-08-16.yaml` đã được code hóa, validate và test nhưng chưa được
phép dùng như giá AloSM production. Finance/Product/Legal phải:

1. Xác nhận hoặc thay thế giá Bike `13.200đ/2 km`, `4.200đ/km` và ý nghĩa `275đ/phút`.
2. Phê duyệt bảng giá riêng cho `CAR_7`; mức hiện tại là suy diễn Car 4 + khoảng 15%, không phải loại xe
   GreenSM công bố chính thức.
3. Xác nhận `per_minute` là thời gian di chuyển hay phí chờ; định nghĩa làm tròn, thời điểm bắt đầu/kết
   thúc và trường hợp đồng thời với `waiting_per_hour`.
4. Phê duyệt từng surcharge, múi giờ, ngày lễ, số lần/điểm dừng và thứ tự cộng phí; xác nhận khác biệt
   phụ phí Bike ban đêm trong nguồn người dùng với trang GreenSM công khai.
5. Legal/Product ký chính sách hủy, hoàn tiền/no-show; cung cấp trạng thái tài xế và mốc thời gian làm
   bằng chứng trước khi backend được phép thu phí.
6. Giao artifact có chữ ký gồm `version`, `effective_from/to`, region, owner, approver, rollback version
   và các golden cases. Sau phê duyệt mới tạo catalog trạng thái `APPROVED`; không sửa nhãn DEMO tại chỗ.

Verify: Finance đối soát golden cases qua API, kiểm tra quote/booking audit giữ nguyên pricing version,
kiểm thử timezone/rounding/boundary và ký biên bản release. Risk nếu bỏ qua: báo sai giá, thu sai phí,
khiếu nại và vi phạm nghĩa vụ công bố giá.

### 2.2 Xác minh pháp nhân và đầu mối liên hệ AloSM

Chủ dự án đã tự phê duyệt policy catalog phiên bản `2026-08-16`; phần nội dung vận hành, RAG,
registration consent, cookie choice và voice consent đã được tích hợp. Tuy nhiên bản nguồn giữ nguyên
415 lần tham chiếu Green SM/GSM và không chứa AloSM. Trước public production, owner phải cung cấp và
xác minh: tên pháp nhân AloSM, mã đăng ký, địa chỉ, hotline, email hỗ trợ, email/DPO xử lý quyền dữ liệu
và kênh khiếu nại. Không được dùng thông tin Green SM/GSM thay thế.

Expected artifact: legal contact sheet có owner/approver/effective date. Verify qua cuộc gọi/email test
và legal sign-off; sau đó cập nhật một policy version mới, không sửa ngược catalog `2026-08-16`.
## 3. Hạ tầng dữ liệu production cần owner/hạ tầng

Kết nối Supabase/Postgres và Alembic đã được kiểm tra thật ngày 2026-08-16: `current` khớp
`0002_handoff_operations` trong lần kiểm tra read-only; code head hiện là `0004_maps_places_routes` và cần thực hiện P0.1/P0.2 trước khi cập nhật trạng thái live. Không cần tạo lại project chỉ để
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

## 10. LiveKit Voice Agent — việc bắt buộc cần owner/hạ tầng (MỚI 2026-08-20)

Branch `feature/voice-ai` (sau merge) đã tích hợp LiveKit native voice pipeline qua `src/voice_agent/`. AI đã viết code, migration `0005_livekit_voice_state` và config — nhưng không thể tự cấp credential LiveKit hoặc chọn STT/TTS provider thật.

### 10.1 Cấp credential LiveKit và chọn runtime

```env
# Bật LiveKit runtime (mặc định là "legacy" để không thay đổi production hiện tại)
VOICE_RUNTIME=livekit

# LiveKit server
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

# Agent name (phải khớp config Room và dispatch)
LIVEKIT_AGENT_NAME=alosm-voice
```

Owner phải:
1. Tạo project LiveKit Cloud hoặc self-host LiveKit Server ≥1.7.
2. Cấp API key/secret theo môi trường (dev/staging/prod); không dùng chung key.
3. Cấu hình Room Agent Dispatch: `agent_name = "alosm-voice"`, `max_participants`, `timeout`.
4. Bật `VOICE_RUNTIME=livekit` chỉ sau khi toàn bộ STT/TTS/LLM provider đã có credential thật (mục 10.2).
5. Verify: Agent connect room, tạo token, event log `session_started`, không leak API secret vào log.

### 10.2 Chọn STT/TTS/LLM provider cho LiveKit pipeline

LiveKit agent cần 3 providers với provider prefix trong model name:

```env
# STT — ví dụ: google/chirp_2 hoặc openai/whisper-1
LIVEKIT_STT_MODEL=google/chirp_2
LIVEKIT_STT_LANGUAGE=vi

# LLM — ví dụ: openai/gpt-4.1-mini
LIVEKIT_LLM_MODEL=openai/gpt-4.1-mini

# TTS — ví dụ: openai/gpt-4o-mini-tts
LIVEKIT_TTS_MODEL=openai/gpt-4o-mini-tts
LIVEKIT_TTS_VOICE=shimmer
LIVEKIT_TTS_LANGUAGE=vi
```

Lưu ý: Model name **BẮT BUỘC** có tiền tố `provider/` (ví dụ `google/`, `openai/`, `elevenlabs/`). Nếu không đúng format, `require_ready()` sẽ fail với `LIVEKIT_STT_MODEL_MUST_USE_PROVIDER_MODEL`.

### 10.3 Điều chỉnh VAD/endpointing cho tiếng Việt

Các giá trị default đã được tuned cho tiếng Việt (ngắt câu dài hơn do tiếng Việt có nhiều pause tự nhiên):

```env
# VAD — giữ default nếu chưa benchmark
LIVEKIT_TURN_DETECTION=vad
LIVEKIT_ENDPOINTING_MIN_DELAY_SECONDS=2.0  # 0.25–3.0
LIVEKIT_ENDPOINTING_MAX_DELAY_SECONDS=3.0  # 0.5–5.0
LIVEKIT_INTERRUPTION_MIN_DURATION_SECONDS=0.5
LIVEKIT_INTERRUPTION_MIN_WORDS=1
```

Owner phải benchmark và điều chỉnh trước go-live để tránh barge-in sai và latency cao (xem `docs/PROBLEMS.md`).

### 10.4 Privacy — ghi âm và lưu transcript

Mặc định tắt hoàn toàn. Chỉ bật sau khi có policy và consent:

```env
# Mặc định false — không bật nếu chưa có Privacy/Legal approval
LIVEKIT_RECORD_AUDIO=false
LIVEKIT_RECORD_TRANSCRIPT=false
```

### 10.5 Chạy LiveKit Agent worker

```powershell
# Dev/test (không kết nối room thật)
uv run python -m src.voice_agent.agent dev

# Production worker (kết nối LiveKit server và nhận room dispatch)
uv run python -m src.voice_agent.agent start
```

**Expected:** log `Connecting to LiveKit server`, `Agent registered`, `Room joined`. Không có `LIVEKIT_URL_MUST_USE_WEBSOCKET_SCHEME` hay `LIVEKIT_LLM_MODEL_MUST_USE_PROVIDER_MODEL` error.

**Bằng chứng đóng mục:** credential trong secret manager, room dispatch config, agent log `session_started`, VAD benchmark report, privacy approval cho record settings.

---

## Mục 11 — Zipformer ASR Streaming (THÊM MỚI 2026-08-20)

### 11.1 Tải model Zipformer

**Tại sao bạn phải làm:** Model Zipformer (file ONNX ~100MB) không được commit vào repo. Phải tải từ HuggingFace và lưu vào `data/models/asr/`.

**Các bước:**

1. Đảm bảo `HUGGINGFACE_TOKEN` đã có trong `.env` (đã có từ trước).

2. Chạy:
   ```powershell
   uv run python scripts/download_model.py
   ```

3. Expected output:
   ```
   ✅ encoder.int8.onnx (xx.x MB)
   ✅ decoder.onnx (x.x MB)
   ✅ joiner.int8.onnx (x.x MB)
   ✅ tokens.txt (x.x MB)
   All required files present! ✅
   ```

4. Nếu model không có `tokens.txt` (một số models dùng `config.json`):
   ```powershell
   # Kiểm tra nội dung file
   Get-Content data/models/asr/sherpa-onnx-*/config.json | Select-Object -First 5
   # Nếu là danh sách tokens, rename:
   Copy-Item data/models/asr/sherpa-onnx-*/config.json data/models/asr/sherpa-onnx-*/tokens.txt
   ```

**Bằng chứng đóng mục:** output `ls data/models/asr/sherpa-onnx-*/` hiển thị 4 file bắt buộc.

---

### 11.2 Chạy ASR Streaming Server

**Tại sao bạn phải làm:** ASR server phải chạy trước khi LiveKit agent có thể dùng Zipformer STT.

**Các bước:**

```powershell
# Terminal riêng (Terminal 1):
uv run uvicorn asr_server.server:app --host 0.0.0.0 --port 9000 --reload
```

**Expected:**
```
ASR server starting model_dir=data/models/asr/...
OnlineRecognizer ready in X.XXs
INFO:     Application startup complete.
```

**Test health:**
```powershell
curl http://localhost:9000/health
# {"status":"ok","model_loaded":true,"model":"...","active_sessions":0}

curl http://localhost:9000/ready
# {"ready":true}
```

**Bằng chứng đóng mục:** `health` trả `model_loaded: true`.

---

### 11.3 Test ASR streaming với WAV file

```powershell
# Cần file WAV tiếng Việt 16kHz mono
uv run python scripts/test_asr_stream.py path/to/test_vietnamese.wav
```

**Expected output (ví dụ):**
```
[0.523s] PARTIAL (first): tôi muốn
[0.890s] PARTIAL: tôi muốn đi từ
[1.234s] PARTIAL: tôi muốn đi từ bách khoa
[1.890s] FINAL: tôi muốn đi từ bách khoa đến hồ tây
```

Nếu không có file WAV test, tạo script tạo audio từ TTS:
```powershell
# Quick test với text-to-WAV (cần ffmpeg + espeak/gTTS)
# Hoặc record từ mic: https://online-voice-recorder.com/
```

---

### 11.4 Switch sang Zipformer STT (optional)

Khi model đã load thành công, có thể switch agent sang dùng Zipformer:

```env
# .env
LIVEKIT_STT_PROVIDER=zipformer
ZIPFORMER_WS_URL=ws://localhost:9000/v1/stt
```

Restart LiveKit agent worker. Verify trong log:
```
Using Zipformer STT url=ws://localhost:9000/v1/stt
```

**Lưu ý:** Nếu Zipformer không đủ chính xác cho tiếng Việt trong điều kiện thực tế, giữ `LIVEKIT_STT_PROVIDER=cloud` (OpenAI gpt-4o-transcribe) là an toàn hơn.

---

### 11.5 Benchmark ASR

Sau khi ASR server chạy, benchmark thực tế:

```powershell
# 1 session
uv run python scripts/benchmark_asr.py test.wav --sessions 1

# 5 concurrent sessions
uv run python scripts/benchmark_asr.py test.wav --sessions 5

# 10 concurrent sessions (stress test)
uv run python scripts/benchmark_asr.py test.wav --sessions 10
```

**Target metrics (CPU - 2 threads):**
- RTF < 0.3x (1 session)
- First partial < 500ms
- First final < 700ms after speech end

Nếu RTF > 1.0x cho 1 session → cần GPU hoặc tối ưu model.

---

### 11.6 GPU VPS (nếu benchmark chứng minh cần)

**Khi nào cần:** Nếu CPU RTF > 0.5x với 5 concurrent sessions.

**Recommended setup:**
- NVIDIA T4 hoặc A10 GPU
- CUDA 12.x runtime
- `SHERPA_PROVIDER=cuda` trong `.env`
- Build ASR Dockerfile với CUDA base image

**Cloud options:**
- Vast.ai (rẻ nhất cho dev/staging)
- RunPod.io
- AWS g4dn.xlarge (T4)
- GCP n1-standard-4 + T4

**Không cần ngay:** Zipformer 30M chạy tốt trên CPU cho < 5 concurrent calls.

---

### 11.7 Production ASR Domain + TLS

**Tại sao bạn phải làm:** Production không thể dùng `ws://IP:9000` plain WebSocket.

**Required:**
1. Domain cho ASR: `asr.yourdomain.com`
2. DNS A record → VPS IP
3. TLS cert (Let's Encrypt via Caddy hoặc Nginx)
4. Reverse proxy: `wss://asr.yourdomain.com/v1/stt` → `ws://localhost:9000/v1/stt`

**Caddy example:**
```
asr.yourdomain.com {
    reverse_proxy localhost:9000
}
```

**Cập nhật .env production:**
```env
ZIPFORMER_WS_URL=wss://asr.yourdomain.com/v1/stt
```

---

### 11.8 Quick Start Development (full stack)

```powershell
# Terminal 1 — ASR Server
uv run uvicorn asr_server.server:app --port 9000

# Terminal 2 — LiveKit Agent
uv run python -m src.voice_agent.server start

# Terminal 3 — FastAPI Backend
uv run uvicorn src.backend.main:app --port 8000 --reload

# Terminal 4 — React Frontend
cd src/frontend && npm run dev
```

Sau đó mở: http://localhost:5173 → đăng nhập → "Gọi AI"

---

### 11.9 Smoke Test đầy đủ

```powershell
uv run python scripts/smoke_test.py
```

Expected:
```
✅ PASS  GET /health → 200  [status=ok]
✅ PASS  GET /health → 200  [model_loaded=True]
✅ PASS  GET /ready → 200 (model loaded)  [{'ready': True}]
✅ PASS  Worker health port 8081
Result: 4/4 checks passed
```

---

## 12. Hạ tầng Bản đồ (Maps, Nominatim & OSRM) Production

Hệ thống Maps (Nominatim Geocoding, OSRM Routing, Leaflet Maps, Pricing/Booking Integration) đã được tích hợp hoàn chỉnh và hoạt động tốt trên môi trường development sử dụng các public OSM endpoint.

Phần việc thuộc trách nhiệm **Owner/DevOps/Hạ tầng** khi đưa lên production tải cao:

### 12.1 Triển khai Self-hosted OSRM & Nominatim (Khuyến nghị cho Production)
Public OSM Nominatim có giới hạn request rate (tối đa 1 req/s). Khi chạy tải cao trong môi trường production, cần dựng cụm container OSRM & Nominatim riêng:

1. **OSRM Container (Docker)**:
   - Tải file dữ liệu OpenStreetMap Việt Nam: `vietnam-latest.osm.pbf` từ Geofabrik.
   - Trích xuất graph routing:
     ```bash
     docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/vietnam-latest.osm.pbf
     docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/vietnam-latest.osrm
     docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/vietnam-latest.osrm
     ```
   - Chạy OSRM server:
     ```bash
     docker run -t -i -p 5000:5000 -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/vietnam-latest.osrm
     ```

2. **Nominatim Container (Docker)**:
   - Dựng container Nominatim với PostgreSQL/PostGIS:
     ```bash
     docker run -d --name nominatim -p 8088:8080 -e PBF_URL=https://download.geofabrik.de/asia/vietnam-latest.osm.pbf -v nominatim-data:/var/lib/postgresql/14/main mediagis/nominatim:4.4
     ```

### 12.2 Cấu hình Production Environment Variables (.env)
```env
MAPS_PROVIDER=osm
NOMINATIM_BASE_URL=http://internal-nominatim:8088
OSRM_BASE_URL=http://internal-osrm:5000
NOMINATIM_USER_AGENT=AloSM/1.0 (ride-hailing; ops@alosm.vn)
MAPS_CACHE_BACKEND=redis
MAPS_CACHE_REDIS_URL=redis://redis:6379/1
```