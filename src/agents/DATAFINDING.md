# DATAFINDING.md — Nghiên cứu nguồn dữ liệu thật cho Agentic AI (Core Agent + RAG)

> Mục đích: liệt kê **chính xác** những chỗ Core Agent/RAG hiện đang chạy bằng dữ
> liệu mô phỏng (deterministic, không phải giả ngẫu nhiên — nhưng vẫn không phải dữ
> liệu thật), và với mỗi chỗ đó, đề xuất **nguồn dữ liệu/API thật cụ thể** để thay
> thế, kèm việc cần làm và ai là người cần làm (kỹ thuật tự lấy được, hay cần
> business/ops cung cấp). Đây là tài liệu NGHIÊN CỨU PHƯƠNG ÁN — chưa code, để đội
> quyết định nguồn nào rồi mới triển khai.
>
> Tài liệu này KHÔNG lặp lại nội dung đã có ở [`mustdo.md`](../../mustdo.md) (Payment
> Gateway, GPS/Maps Provider, OPENAI_API_KEY, SMS) — mà đào sâu hơn vào phần
> **agentic AI/RAG cụ thể**: cần dữ liệu gì, định dạng gì, lấy ở đâu, migrate vào
> code hiện có (`src/agents/`, `src/backend/services/`) như thế nào mà không phá
> hợp đồng (`AgentGuardrails`, `FAQWorkflow.min_score`, schema `AgentInput`/
> `AgentState`) đã có.

## 0. Cách đọc bảng hiện trạng

Mỗi mục dưới đây đều trả lời 4 câu hỏi: **(1) Hiện tại lấy dữ liệu từ đâu — (2) Vì
sao chưa phải dữ liệu thật — (3) Dữ liệu thật cần có hình dạng gì — (4) Lấy ở đâu /
làm sao.** Toàn bộ code liên quan tự đọc trực tiếp trong repo (không suy đoán) tính
đến thời điểm viết tài liệu này.

---

## 1. Bản đồ hiện trạng (tổng quan nhanh)

| Thành phần | File | Trạng thái | Cần dữ liệu thật? |
|---|---|---|---|
| Hiểu ngôn ngữ tự nhiên (LLM) | `understanding/openai.py`, `understanding/factory.py` | **Gọi OpenAI Responses API thật** — chỉ thiếu `OPENAI_API_KEY` thật | Không cần "tìm data", chỉ cần key thật (xem `mustdo.md` mục 6) |
| Viết lại câu theo ngữ cảnh (rewrite) | `understanding/rewrite_openai.py` | Gọi OpenAI thật, tắt mặc định (`AGENT_REWRITE_ENABLED=false`) | Không cần data, cần key thật + quyết định bật |
| Gợi ý loại xe (vehicle recommendation) | `vehicle_recommendation.py` | Gọi OpenAI thật, tự tắt (`NoRecommendation`) khi thiếu key | Không cần data, cần key thật |
| Chính sách SĐT (`phone_policy.py`) | regex | **Đã là logic thật** (đúng đầu số di động VN 03/05/07/08/09) | Không cần |
| Chính sách địa chỉ mơ hồ (`location_policy.py`) | regex | **Đã là logic thật** | Không cần |
| Tìm địa điểm (`search_place`) | `place_search_service.py` + `data/gazetteer/place_names.json` | 23 địa danh mẫu, KHÔNG có toạ độ, so khớp chuỗi con | **Cần** — mục 2 |
| Giá cước / khoảng cách (`get_vehicle_options`, `estimate_fare`) | `pricing_service.py` | Khoảng cách suy từ hash (không phải GPS thật); biểu giá VNĐ/km tự đặt | **Cần** — mục 3 |
| Kiến thức FAQ (RAG) | `knowledge_service.py` + `src/agents/rag/` | 6 tài liệu tôi tự viết (khớp nội dung các trang khác trong app), retriever so khớp từ khoá (không embedding) | **Cần** — mục 4 |
| Bộ dữ liệu đánh giá (eval) | `src/agents/eval/datasets/readiness_v1.json` | 8 kịch bản tôi tự soạn, tool result giả định | **Cần** — mục 6 |

---

## 2. `search_place` — địa danh & toạ độ thật

**Hiện tại:** `PlaceSearchService.search()` đọc `data/gazetteer/place_names.json` —
file này tự ghi rõ trong `_comment`: *"SEED DATA — vài chục địa danh TP.HCM phổ biến
để pipeline chạy demo được. CHƯA phải danh sách thật của AloSM"*. Chỉ có `place_names`
(chuỗi tên), **không có lat/lng, không có địa chỉ đầy đủ, không có bán kính vùng phủ
sóng dịch vụ**. `place_id` là hash ổn định của tên (`place_id_for()`), không phải ID
thật từ một hệ thống bản đồ nào.

**Vì sao chưa đủ cho production:** khách nói một địa chỉ không nằm trong 23 địa danh
mẫu → agent chỉ echo lại nguyên văn làm 1 candidate duy nhất, không thật sự "tìm
kiếm" hay xác thực địa chỉ đó có tồn tại/nằm trong vùng phục vụ hay không.

**Dữ liệu thật cần có:**
- Tên địa điểm + địa chỉ đầy đủ (chuẩn hoá tiếng Việt có dấu)
- Toạ độ `lat`/`lng` thật (bắt buộc để mục 3 tính khoảng cách thật)
- Loại địa điểm (POI, địa chỉ nhà, giao lộ...) để agent phân biệt "địa danh nổi
  tiếng" và "địa chỉ tự do"
- Vùng phủ sóng dịch vụ (polygon/bán kính) để biết khi nào nên từ chối lịch sự thay
  vì nhận chuyến ngoài vùng

**Nguồn thật để nghiên cứu (xếp theo chi phí/độ khó tăng dần):**

| Nguồn | Chi phí | Ghi chú |
|---|---|---|
| **OpenStreetMap Nominatim/Overpass** | Miễn phí (rate-limit thấp trên server công cộng, self-host được) | Phủ TP.HCM khá tốt cho địa danh lớn; địa chỉ nhà dân đôi khi thiếu. Điểm khởi đầu tốt, không cần đăng ký, không cần billing |
| **Goong Maps API** (Việt Nam) | Có gói free tier | Chuyên VN, geocoding + autocomplete tiếng Việt có dấu tốt hơn OSM cho địa chỉ nhà dân; dùng phổ biến ở các dự án ride-hailing VN |
| **VietMap API** | Có gói free tier | Tương tự Goong, thêm dữ liệu giao thông VN |
| **Google Places/Geocoding API** | Trả phí theo request (có billing) | Đầy đủ nhất, nhưng cần thẻ thanh toán + giới hạn theo domain/key (đã ghi trong `mustdo.md` mục 3 cho phần Maps Provider của Tracking — **nên dùng chung 1 API key Google Maps cho cả Tracking lẫn search_place nếu chọn Google**, tránh xin 2 key riêng) |
| **Dữ liệu nội bộ AloSM** (nếu có) | — | Danh sách điểm đón/trả hay dùng thật, trụ sở, khu vực phủ sóng — chính xác nhất nhưng cần đội vận hành cung cấp, không tự tra cứu được |

**Việc cần làm khi có nguồn:**
1. Viết 1 provider mới (vd `RealGeocodingProvider`) implement cùng interface trả về
   của `PlaceSearchService.search()` (`place_id`/`display_name`/`address`), cộng
   thêm `lat`/`lng` vào dict trả về.
2. **Lưu ý hợp đồng cũ:** `place_id_for()` hiện là hash-của-tên, được
   `AgentGuardrails` dùng để đối chiếu `pickup_place_id`/`destination_place_id` đã
   xác nhận với state đã lưu (chặn agent tự đổi địa điểm khi gọi tool). Nếu đổi sang
   `place_id` thật từ API ngoài (không còn là hash tất định của tên), phải giữ
   nguyên tính chất "cùng 1 địa điểm luôn ra cùng 1 `place_id` giữa các lượt gọi
   trong 1 phiên" — kiểm tra kỹ `guardrails.py` trước khi đổi, đừng chỉ đổi
   `place_search_service.py` một mình.
3. Thêm cache (địa danh ít đổi) để không gọi API ngoài mỗi lần khách gõ trùng địa chỉ.

---

## 3. Khoảng cách & giá cước — routing thật + biểu giá thật

**Hiện tại:** `pricing_service.py` tự ghi rõ trong comment: *"Chưa tích hợp
Maps/routing API thật... Khoảng cách/giá cước suy ra DETERMINISTIC theo hash, không
phải số liệu GPS thật"*. Biểu giá (`_FARE_PER_KM_VND`, `_BASE_OPEN_FARE_VND`,
`_AVG_SPEED_KMH`) là số tôi tự đặt ra để có công thức hợp lý, **không phải bảng giá
kinh doanh thật của AloSM**.

Đây là **2 loại dữ liệu riêng biệt**, cần 2 nguồn khác nhau:

### 3a. Khoảng cách/thời gian di chuyển thật (kỹ thuật tự lấy được)
Cần toạ độ thật từ mục 2 trước, rồi mới gọi routing API:

| Nguồn | Chi phí | Ghi chú |
|---|---|---|
| **OSRM** (Open Source Routing Machine, tự host) | Miễn phí, cần tự host + tải OSM road network VN | Không phụ thuộc API ngoài, phù hợp nếu muốn tự chủ hạ tầng |
| **Goong/VietMap Directions API** | Free tier | Đi kèm luôn nếu đã chọn Goong/VietMap cho mục 2 — nên dùng chung 1 nhà cung cấp cho cả geocoding lẫn routing để nhất quán toạ độ |
| **Google Distance Matrix API** | Trả phí | Chính xác nhất, cùng hệ sinh thái nếu chọn Google ở mục 2 |

### 3b. Biểu giá kinh doanh thật (**không phải việc kỹ thuật — cần business/ops/tài
chính cung cấp**)
Đây là dữ liệu **không thể tự tra cứu hay bịa ra** vì nó là quyết định kinh doanh:
- Giá mở cửa (base fare) theo từng loại xe
- Đơn giá VNĐ/km theo từng loại xe (xe máy / ô tô 4 chỗ / ô tô 7 chỗ)
- Phí chờ, phí huỷ chuyến (đã nhắc tới trong FAQ nhưng chưa có con số cụ thể)
- Chính sách giá giờ cao điểm (surge) — hiện hoàn toàn chưa có khái niệm này trong
  `PricingService`
- Giá tối thiểu/tối đa

**Việc cần làm:** xin bảng giá chính thức từ đội sản phẩm/vận hành của AloSM. Nếu
AloSM là dự án capstone chưa có bảng giá kinh doanh thật, đề xuất: tham chiếu công
khai biểu giá thị trường VN hiện hành (Grab/Be/Xanh SM đều công bố khoảng giá/km
theo loại xe) làm cơ sở hiệu chỉnh cho một bảng giá **được tài liệu hoá rõ ràng là
"giả định chờ phê duyệt"** — không âm thầm dùng số tự đặt như hiện tại mà không ghi
chú nguồn.

---

## 4. Kiến thức FAQ (RAG) — tài liệu chính sách chính thức

**Hiện tại:** `knowledge_service.py` có 6 `KnowledgeDocument` (thanh toán, huỷ
chuyến, giá cước, an toàn, quyền riêng tư, đổi điểm đón) — nội dung tôi tự viết,
khớp với những gì các trang khác trong app hiển thị (`ProfilePage`, `PaymentPage`,
`TrackingPage`), nhưng **không xuất phát từ một văn bản chính sách chính thức nào
của AloSM**. Retriever (`KeywordFaqRetriever`) so khớp từ khoá có lọc từ dừng tiếng
Việt — không dùng embedding, không gọi API ngoài.

**`FAQWorkflow.min_score = 0.75`** (`src/agents/workflows/faq.py`) là ngưỡng chống
hallucination cố ý — đã quyết định **không hạ thấp**, giữ nguyên khi mở rộng dữ liệu.

**Dữ liệu thật cần có:** bộ văn bản chính sách chính thức — Điều khoản dịch vụ,
Chính sách quyền riêng tư, Chính sách huỷ chuyến, Chính sách an toàn, Chính sách
thanh toán/hoàn tiền — ở dạng có thể chunk thành nhiều `KnowledgeDocument`
(`document_id`, `content`, `source`, `metadata` — schema đã có sẵn ở
`src/agents/rag/knowledge_base.py`, không cần đổi).

**Nguồn:** đội pháp lý/sản phẩm AloSM cung cấp văn bản chính thức (PDF/Docs). Nếu
capstone chưa có, tối thiểu nên viết các chính sách này **một lần, tập trung**
(thay vì rải rác trong code như hiện tại) thành file nguồn (vd
`src/agents/rag/data/policies/*.md`), rồi build `KnowledgeDocument` từ đó — để khi
có bản chính thức thật, chỉ cần thay nội dung file, không sửa code.

**Khi corpus lớn hơn vài chục tài liệu — cần nâng cấp retriever:**
So khớp từ khoá (hiện tại) sẽ không scale khi có nhiều tài liệu nội dung gần giống
nhau. `CHROMA_PERSIST_DIR` đã có sẵn trong `.env.example`/`src/backend/config.py`
nhưng **hiện chưa được `src/agents/rag/` dùng ở đâu cả** (đã kiểm tra — không có
import Chroma/Pinecone nào trong `src/agents` hay `src/backend`). Khi có corpus
thật đủ lớn:
1. Chọn embedding provider: `OpenAI text-embedding-3-small` (đơn giản, cùng hệ với
   `OPENAI_API_KEY` đã có) hoặc mô hình mã nguồn mở hỗ trợ tiếng Việt tốt (vd
   `BAAI/bge-m3`, chạy local, không cần API ngoài).
2. Viết `EmbeddingRetriever(BaseRetriever)` mới trong `src/agents/rag/retriever.py`,
   dùng `CHROMA_PERSIST_DIR` làm nơi lưu vector index.
3. Giữ `KeywordFaqRetriever` làm fallback khi embedding lỗi/timeout (đúng pattern
   `ResilientUnderstandingService` đã dùng cho `understanding/`).

---

## 5. LLM hiểu ngôn ngữ / viết lại câu / gợi ý xe — đã thật, chỉ thiếu key

Không cần "tìm dữ liệu" — 3 chỗ này (`understanding/openai.py`,
`understanding/rewrite_openai.py`, `vehicle_recommendation.py`) đã gọi thẳng OpenAI
Responses API thật với `text_format` (structured output) thật, có fallback an toàn
(`RuleBasedUnderstanding`, `NoRecommendation`) khi tắt hoặc thiếu key. Việc còn lại
đã có sẵn ở `mustdo.md` mục 6 — chỉ cần `OPENAI_API_KEY` thật. Lưu ý khi bật thật:
- `AGENT_LLM_MODEL=gpt-5.6-luna` trong `.env.example` — xác nhận lại tên model thật
  khả dụng với key thật tại thời điểm triển khai (tên/alias model đổi theo thời gian).
- `AGENT_REWRITE_ENABLED=false` mặc định tắt — cần quyết định có bật hay không (bật
  thì tốn thêm 1 lượt gọi LLM/turn hội thoại) trước khi coi đây là "xong".

---

## 6. Bộ dữ liệu đánh giá (eval) — hội thoại thật

**Hiện tại:** `src/agents/eval/datasets/readiness_v1.json` — 8 kịch bản
(`ConversationEvaluationCase`) tôi tự soạn, tool result được mock cứng trong từng
turn để evaluator chạy được không cần backend thật.

**Dữ liệu thật cần có:** transcript hội thoại thật từ người dùng thật (pilot/thử
nghiệm nội bộ trước) — đặc biệt các ca khó: lỗi ASR (nói ngọng/giọng vùng miền bị
nhận sai chữ, feed vào `repair.py`), người dùng đổi ý giữa chừng ("khoan, tôi muốn
đổi..."), câu hỏi FAQ lẫn với câu ra lệnh (đã ghi nhận 1 trường hợp thật: câu hỏi
chứa từ "huỷ" đôi khi bị `repair.py` hiểu nhầm thành lệnh huỷ chuyến — xem mục hạn
chế đã biết trong `TIENTRINH.md`).

**Lưu ý bắt buộc khi thu thập:** mọi transcript thật trước khi đưa vào eval
dataset/commit vào repo **phải qua `redact_pii`/`redact_pii_data`
(`src/agents/guardrails.py`)** để loại SĐT/thông tin cá nhân thật của người dùng —
không commit dữ liệu hội thoại thật chưa lọc PII lên git.

---

## 7. Không cần tìm dữ liệu (liệt kê để tránh làm lại)

- `phone_policy.py`, `location_policy.py`: logic regex thuần, đã đúng theo quy tắc
  đầu số di động VN thật — không phụ thuộc dữ liệu ngoài.
- `guardrails.py`, `context.py`/`history.py`/`repair.py`: logic điều phối trạng
  thái, không phải nguồn dữ liệu.

---

## 8. Thứ tự ưu tiên đề xuất

| # | Việc | Ai làm | Vì sao ưu tiên |
|---|---|---|---|
| 1 | `OPENAI_API_KEY` thật | Bất kỳ ai có quyền tạo key (đã có hướng dẫn ở `mustdo.md` mục 6) | Mở khoá cùng lúc cả 3: hiểu ngôn ngữ, rewrite, gợi ý xe — công sức thấp nhất, lợi ích cao nhất |
| 2 | Bảng giá cước thật | Đội sản phẩm/vận hành/tài chính AloSM | Là dữ liệu kinh doanh, không ai tự bịa được — cần xin sớm vì phụ thuộc quy trình phê duyệt ngoài kỹ thuật |
| 3 | Geocoding + routing thật (chọn 1 nhà cung cấp cho cả 2, xem mục 2 & 3a) | Kỹ thuật tự nghiên cứu/đăng ký | Dùng chung 1 provider tránh lệch toạ độ giữa search_place và tính khoảng cách |
| 4 | Văn bản chính sách chính thức cho RAG | Đội pháp lý/sản phẩm cung cấp, kỹ thuật chunk hoá | Cải thiện độ tin cậy câu trả lời FAQ, không ảnh hưởng phần khác |
| 5 | Nâng cấp retriever sang embedding | Kỹ thuật, chỉ làm khi mục 4 đã có corpus đủ lớn | Không cần thiết khi corpus còn nhỏ (< ~20 tài liệu), làm sớm là tối ưu hoá sớm không cần thiết |
| 6 | Transcript hội thoại thật cho eval | Cần người dùng thật dùng thử trước (pilot) | Phụ thuộc có người dùng thật, không thể làm trước các mục trên |

---

## 9. Rủi ro cần tránh khi bổ sung dữ liệu thật

- **Đừng hạ `FAQWorkflow.min_score`** để "dễ trả lời hơn" khi thêm tài liệu mới —
  nếu tài liệu mới không được retrieve đủ điểm, sửa nội dung tài liệu (viết tự
  nhiên, đúng từ khoá câu hỏi thật) chứ không sửa ngưỡng.
- **Đừng tự bịa toạ độ/bảng giá rồi âm thầm dùng như thật** — nếu bắt buộc phải có
  số liệu tạm trước khi có nguồn chính thức, ghi rõ trong code/comment đây là giả
  định tạm (đúng cách `pricing_service.py`/`place_search_service.py` hiện tại đã tự
  ghi chú, không được thay bằng số liệu "trông thật" mà không ghi nguồn).
- **Đừng thay đổi hợp đồng `place_id`/`AgentGuardrails`** khi đổi nguồn geocoding mà
  không rà lại toàn bộ chỗ dùng — xem mục 2, việc 2.
- **Không commit transcript thật chưa qua `redact_pii`.**

---

## 10. Tham chiếu chéo

- [`mustdo.md`](../../mustdo.md) — checklist tổng: Payment Gateway (mục 2), GPS/Maps
  Provider cho Tracking (mục 3), OPENAI_API_KEY (mục 6).
- [`docs/voice-ai/mustdo_voice.md`](../../docs/voice-ai/mustdo_voice.md) — phần
  thoại/giọng nói (ASR/TTS), không trùng phạm vi tài liệu này.
- [`src/agents/docs/BACKEND_INTEGRATION.md`](docs/BACKEND_INTEGRATION.md) — hợp
  đồng tool dispatch mà mọi nguồn dữ liệu mới phải tuân theo.
- [`TIENTRINH.md`](../../TIENTRINH.md) — nhật ký các quyết định đã thực hiện trong
  dự án (mục "Nhập Core Agent...") có ghi lại việc đã thay các service mock cũ
  (echo nguyên câu, giá cố định 85.000đ, 2 câu FAQ cứng) bằng bản mô phỏng có căn cứ
  như mô tả ở tài liệu này — tài liệu này là bước tiếp theo: từ "mô phỏng có căn cứ"
  lên "dữ liệu thật".
