# AloSM

## Đề bài

### GSM-08 — AI Agent Tổng đài giọng nói đặt xe & tra cứu Dịch vụ gọi xe X

**Thực trạng:** Nhiều khách, đặc biệt là người lớn tuổi, quen gọi tổng đài đặt xe. Nhân viên trực điện thoại tốn nhiều nguồn lực và tổng đài dễ nghẽn vào giờ cao điểm.

**Vấn đề:** Cần xây dựng AI Agent giọng nói tiếp nhận cuộc gọi, có khả năng:

- nghe yêu cầu đặt xe, tra cứu chuyến và hỏi cước;
- xác nhận điểm đón, điểm đến bằng lời;
- gọi tool đặt xe và đọc lại kết quả xác nhận;
- chuyển cuộc gọi cho tổng đài viên khi cần.

**Ràng buộc:**

- HITL/chuyển tổng đài viên khi nhận diện kém hoặc yêu cầu phức tạp;
- bảo mật bản ghi âm và dữ liệu PII;
- bảo đảm độ chính xác STT tiếng Việt, đặc biệt khi nhận diện và xác nhận địa chỉ;
- độ trễ hội thoại thấp và hỗ trợ barge-in;
- kiểm soát chi phí STT/TTS.

## Công nghệ định hướng

- STT tiếng Việt: Whisper/PhoWhisper;
- TTS: ElevenLabs/Google;
- LLM và LangGraph;
- tool geocoding: Mapbox/Google Places để xác nhận địa chỉ;
- PostgreSQL lưu dữ liệu chuyến;
- backend FastAPI kết hợp WebRTC/WebSocket streaming;
- frontend React cho web call;
- deploy trên Fly.io.

## Yêu cầu

### Cơ bản

- Web call đã deploy, có đăng nhập cho khách hàng và tổng đài viên;
- luồng thoại đặt xe, xác nhận địa chỉ và đọc kết quả;
- transcript và memory hội thoại.

### Nâng cao

- barge-in và xử lý ngắt lời;
- HITL chuyển người thật kèm đầy đủ ngữ cảnh cần thiết;
- cảnh báo khi độ tin cậy nhận dạng thấp;
- fallback sang nhập tay khi STT lỗi;
- guardrail bảo vệ PII.

## Mục tiêu trọng tâm

Mục đích chính của đề là xây dựng **Voice Agent**. Vì vậy, năng lực cần được ưu tiên và làm tốt nhất là vòng lặp hội thoại giọng nói:

```text
Nghe audio
→ nhận dạng lời nói
→ hiểu và quản lý hội thoại
→ quyết định/gọi tool khi cần
→ tạo câu trả lời
→ phát giọng nói
```

Các tiêu chí cốt lõi gồm:

- nhận dạng tiếng Việt và địa danh đủ chính xác;
- phản hồi voice-to-voice có độ trễ thấp;
- streaming ổn định;
- xử lý ngắt lời tự nhiên;
- duy trì đúng session và ngữ cảnh hội thoại;
- xác nhận rõ ràng trước hành động quan trọng;
- fallback và chuyển người thật an toàn;
- bảo vệ audio, transcript và PII.

## Vấn đề về phạm vi hiện tại

Scope của nhóm đang có dấu hiệu lan sang nhiều bài toán phụ trợ như:

- Map API và lựa chọn nhà cung cấp bản đồ;
- resolve và chuẩn hóa địa chỉ;
- geocoding/routing;
- ước lượng quãng đường, ETA và giá;
- pricing catalog, promotion, fleet và persistence mở rộng.

Các phần này cần thiết cho sản phẩm đặt xe hoàn chỉnh, nhưng bản thân mỗi phần là một bài toán lớn và có thể thuộc ownership của team dịch vụ nghiệp vụ khác. Nếu nhóm Voice Agent tự đi quá sâu vào các miền này, nguồn lực sẽ bị phân tán trong khi những vấn đề cốt lõi hiện tại vẫn chưa được giải quyết tốt, đặc biệt là:

- nhận diện địa danh chưa chính xác;
- latency voice-to-voice còn cao;
- realtime pipeline và streaming chưa thực sự tự nhiên;
- barge-in/HITL chưa được chứng minh end-to-end;
- chất lượng hội thoại voice chưa đạt mức tổng đài thực tế.

## Hướng cần thảo luận

Thay vì tiếp tục tự triển khai toàn bộ core component của voice stack, nhóm cân nhắc thử nghiệm framework Voice Agent có sẵn để tận dụng:

- realtime audio pipeline;
- streaming STT/TTS;
- session và orchestration;
- turn detection;
- interruption/barge-in;
- transport WebRTC/WebSocket;
- observability và lifecycle của cuộc gọi.

Khi đó nhóm có thể tập trung nguồn lực vào những phần tạo giá trị trực tiếp cho đề:

- đánh giá và cải thiện ASR tiếng Việt;
- nhận dạng địa danh và critical entities;
- giảm latency voice-to-voice;
- thiết kế hội thoại đặt xe tự nhiên;
- tích hợp Voice Agent với Agent Core;
- xác nhận địa chỉ, giá và booking qua contract/tool rõ ràng;
- HITL, fallback và PII guardrail.

## Câu hỏi quyết định kiến trúc

1. Nhóm có nên xác định lại Voice Agent là scope chính, còn Maps/Pricing/Booking chỉ là external tool contract hoặc mock service không?
2. Có nên dùng framework Voice Agent có sẵn cho realtime pipeline thay vì tiếp tục tự xây toàn bộ transport, session, VAD và orchestration không?
3. Nếu thử framework, tiêu chí benchmark và điều kiện giữ/bỏ framework là gì?
4. Agent Core hiện tại sẽ được giữ làm business/conversation brain hay thay thế một phần bởi orchestration của framework?
5. Demo cuối kỳ cần chứng minh chiều sâu kỹ thuật nào: sản phẩm đặt xe đầy đủ hay chất lượng Voice Agent end-to-end?

## Nguyên tắc scope đề xuất để thảo luận

Voice Agent sở hữu:

- audio ingress/egress;
- VAD, turn detection và barge-in;
- STT/TTS orchestration;
- transcript confidence và critical-entity validation;
- conversation session và kết nối với Agent Core;
- HITL/fallback;
- latency, quality metrics và PII handling.

Voice Agent chỉ tích hợp qua contract với:

- place search/geocoding;
- routing và ETA;
- pricing/quote;
- booking/trip provider;
- authentication và durable trip storage.

Các dịch vụ ngoài scope có thể dùng mock hoặc adapter tối thiểu trong demo, miễn là không giả mạo kết quả và vẫn thể hiện đúng tool-calling contract.

## Phản hồi của mentor

Mentor đồng ý rằng Maps và Booking chỉ cần được triển khai ở mức **integration**:

- API bản đồ nên ưu tiên sử dụng dịch vụ có sẵn;
- không cần tự xây bài toán bản đồ hoặc geocoding;
- estimate quãng đường, ETA và giá có thể dùng fake data/deterministic data cho demo;
- booking có thể dùng fake backend hoặc mock provider;
- các phần tích hợp vẫn cần contract rõ ràng để thể hiện đúng luồng gọi tool của Voice Agent.

Những phần mentor đánh giá cần làm sâu gồm:

1. Streaming audio và quản lý session.
2. VAD/turn detection, barge-in và xử lý khi người dùng ngắt lời.
3. ASR tiếng Việt, đặc biệt với địa danh, giọng vùng miền và môi trường nhiễu.
4. Quản lý state hội thoại: điểm đón, điểm đến, loại xe, sửa thông tin và xác nhận.
5. Voice-to-voice latency, fallback và handoff sang tổng đài viên.
6. Đo ASR accuracy, task completion rate và latency theo từng stage.

Khối lượng trên đã đủ lớn cho phạm vi đề tài. Không nên tiếp tục mở rộng sâu sang Maps, Routing, Pricing, Fleet hoặc Booking backend khi các năng lực Voice Agent cốt lõi chưa hoàn thiện.

## Thứ tự triển khai đã thống nhất

Nguyên tắc thực hiện là **happy path end-to-end đủ tốt trước, sau đó mới mở rộng edge case**.

### Giai đoạn 1 — Happy path end-to-end

Hoàn thiện một luồng đặt xe bằng giọng nói ổn định:

```text
Người dùng bắt đầu web call
→ hệ thống nhận audio streaming
→ phát hiện người dùng đang nói/kết thúc lượt nói
→ STT tạo transcript
→ Agent thu thập điểm đón, điểm đến và loại xe
→ tool bản đồ có sẵn resolve địa chỉ
→ fake service trả quãng đường, giá và kết quả booking
→ Agent đọc lại thông tin để người dùng xác nhận
→ TTS đọc kết quả đặt xe
→ transcript và state được lưu theo session
```

Happy path chỉ được xem là đủ tốt khi:

- session không bị mất hoặc lẫn trạng thái giữa các lượt;
- điểm đón, điểm đến và loại xe được cập nhật đúng;
- người dùng có thể sửa thông tin trước khi xác nhận;
- booking chỉ xảy ra sau xác nhận rõ ràng;
- phản hồi được phát bằng voice;
- latency từng stage được ghi nhận;
- toàn bộ luồng có thể chạy lặp lại ổn định trong demo.

### Giai đoạn 2 — Realtime interaction

Sau khi happy path ổn định, tập trung vào:

- streaming thay vì chờ gửi toàn bộ file audio;
- VAD và turn detection;
- barge-in;
- dừng/cancel TTS đang phát khi người dùng ngắt lời;
- xử lý transcript hoặc action đang chạy dở;
- bảo toàn state sau interruption.

### Giai đoạn 3 — Quality, fallback và HITL

Tiếp tục hoàn thiện:

- confidence của ASR và critical entities;
- fallback sang nhập tay khi STT thất bại;
- handoff sang tổng đài viên kèm context cần thiết;
- bảo vệ audio, transcript và PII;
- timeout, provider failure và session recovery.

### Giai đoạn 4 — Noise và unexpected behavior

Chỉ thực hiện sau khi ba giai đoạn trên đã đạt baseline:

- tiếng ồn môi trường;
- giọng vùng miền;
- nói lắp, nói thiếu hoặc thay đổi ý nhiều lần;
- người dùng nói ngoài phạm vi;
- audio rỗng, mất kết nối hoặc provider trả kết quả bất thường;
- các edge case hội thoại khác.

## Chỉ số đánh giá bắt buộc

### Chất lượng ASR

- WER/CER trên tập audio tiếng Việt phù hợp;
- tỷ lệ nhận đúng địa danh và critical entities;
- kết quả theo từng nhóm giọng hoặc điều kiện audio khi có dataset tương ứng;
- tỷ lệ transcript phải yêu cầu người dùng nhắc lại.

### Chất lượng hoàn thành tác vụ

- task completion rate của happy path;
- tỷ lệ hoàn thành sau khi sửa điểm đón, điểm đến hoặc loại xe;
- tỷ lệ booking chỉ được tạo sau xác nhận hợp lệ;
- tỷ lệ fallback và handoff đúng lý do.

### Latency theo từng stage

- audio ingress/buffering;
- VAD endpointing;
- STT;
- Agent/LLM;
- tool execution;
- TTS time-to-first-audio;
- tổng latency voice-to-voice;
- p50/p95 thay vì chỉ báo cáo một lần chạy tốt nhất.

## Scope chốt sau phản hồi mentor

### Làm sâu

- streaming audio và session;
- VAD, turn detection và barge-in;
- ASR tiếng Việt và địa danh;
- conversation state và correction/confirmation;
- voice-to-voice latency;
- fallback và HITL;
- metrics/evaluation cho accuracy, completion và latency.

### Chỉ tích hợp hoặc mô phỏng

- Maps/geocoding: dùng API có sẵn;
- route/distance/ETA: fake hoặc deterministic data;
- pricing/quote: fake hoặc deterministic data;
- booking/trip provider: fake backend có contract và trạng thái rõ ràng;
- không đi sâu vào fleet, dispatch, promotion, payment hoặc production routing.

### Chưa ưu tiên

- môi trường nhiễu phức tạp;
- toàn bộ giọng vùng miền ở quy mô lớn;
- unexpected behavior và long-tail edge cases;
- production-grade Maps/Pricing/Booking;
- các chức năng sản phẩm không trực tiếp chứng minh năng lực Voice Agent.

## Định hướng refactor framework Voice Agent

Sau khi đối chiếu source hiện tại với LiveKit Agents, kiến trúc đề xuất là dùng
**LiveKit làm framework duy nhất cho toàn bộ Voice Agent runtime**, thay vì chỉ dùng
LiveKit như transport rồi giữ một voice/tool framework tự triển khai chạy bên cạnh.

Mục tiêu kiến trúc:

```text
React LiveKit client
→ LiveKit Room/WebRTC
→ AgentServer/AgentSession
→ AloSM Agent/AgentTask
→ LiveKit function tools
→ AloSM application services
→ PostgreSQL hoặc fake integration
```

LiveKit sẽ sở hữu media transport, RoomIO, session lifecycle, VAD/endpointing,
interruption, STT–LLM–TTS orchestration, chat context, tool loop, events và metrics.
AloSM chỉ bổ sung code đặc thù tại extension point chính thức của framework:

- typed booking state và typed task result;
- search place, quote, booking, trip và handoff tools;
- explicit confirmation, idempotency và PII policy;
- địa danh/confidence hook;
- application service, persistence và evaluation dataset.

Không giữ đồng thời LiveKit tool loop và `SessionService`/`AgentToolExecutor` tool
loop trong cùng cuộc gọi. Kiến trúc đích là full LiveKit-native, nhưng migration
thực hiện theo vertical slice, benchmark xong mới xóa runtime cũ.

Kiến trúc đã chốt, mapping source và acceptance gate nằm tại
[`LIVEKIT_MIGRATION_IMPLEMENTATION.md`](./LIVEKIT_MIGRATION_IMPLEMENTATION.md); trạng
thái hiện tại và đường đọc cho coding agent nằm tại
[`CODING_AGENT_HANDOFF.md`](./CODING_AGENT_HANDOFF.md).

Quyết định cuối cùng và thứ tự dành cho coding agent nằm tại
[`LIVEKIT_MIGRATION_IMPLEMENTATION.md`](./LIVEKIT_MIGRATION_IMPLEMENTATION.md). Kiến
trúc đã chốt là **một `AloSMAgent` + `BookingTask` + LiveKit function tools**, không
dùng multi-agent cho scope hiện tại.
