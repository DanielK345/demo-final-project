# Modern Voice Agent Coding Rules

Tài liệu này là luật làm việc cho mọi thay đổi trong `src/agents`. Mục tiêu là giữ
agent theo kiểu voice agent booking hiện đại: LLM điều khiển hội thoại bằng tool
calling, typed state giữ dữ liệu, deterministic policy bảo vệ nghiệp vụ.

## 1. Ranh giới hệ thống

Agent là core hội thoại. Agent không phải Backend, không phải Frontend, không phải
Voice runtime.

Agent được phép:

- nhận `AgentInput`;
- đọc `AgentState`;
- gọi semantic tools nội bộ;
- trả `AgentAction`;
- nhận `ToolResult` từ Backend;
- reduce tool result vào typed state;
- hỏi khách hoặc trả lời khách bằng message ngắn.

Agent không được:

- gọi database trực tiếp;
- gọi Maps API trực tiếp;
- gọi booking/dispatch/payment API trực tiếp;
- tự tạo booking trong code agent;
- tự tính giá thật;
- tự tạo ETA thật;
- tự xử lý STT/TTS/audio;
- sửa flow Frontend;
- phụ thuộc vào mock backend riêng trong production path.

Luồng đúng:

```text
Frontend/Voice
-> Backend session API
-> AgentInput + AgentState
-> Agent
-> AgentAction(CALL_TOOL | ASK_USER | RESPOND | HANDOFF | END_SESSION)
-> Backend executes external tool
-> ToolResult
-> Agent reduces result and continues
```

## 2. Kiến trúc bắt buộc

Code agent phải đi theo 3 lớp trách nhiệm:

```text
LLM/tool loop
-> typed state/capability reducers
-> deterministic policy/guardrails
```

LLM/tool loop:

- LLM hiểu câu người dùng và chọn semantic tool.
- LLM không được tự bịa dữ liệu nghiệp vụ.
- LLM không tự tạo side effect bằng text.
- Nếu cần dữ liệu thật, LLM phải gọi tool.

Typed state:

- Mọi dữ liệu hội thoại sống trong `AgentState` và state capability tương ứng.
- Booking data nằm trong typed booking state.
- Trip lookup data nằm trong typed trip state.
- FAQ/RAG data nằm trong typed FAQ state.
- Không dùng dict/string rời rạc để lưu state nghiệp vụ mới nếu có thể model hóa typed state.

Deterministic policy/guardrails:

- Chặn side effect chưa xác nhận.
- Chặn tool call không khớp workflow.
- Chặn create/cancel booking nếu params không khớp state.
- Chặn clear pending side effect khi chưa có `ToolResult`.
- Xử lý confirmation gates như `có`, `ừ`, `xác nhận`, `ok` khi đang chờ xác nhận.

## 3. Cách tổ chức code

Vai trò thư mục:

```text
src/agents/agent.py
```

Public entrypoint. Tích hợp core agent, guardrails, compatibility path. Không nhét
workflow logic dài vào đây.

```text
src/agents/core/
```

Core orchestration: model adapter, session projection, registry, policy, guardrails,
instructions.

```text
src/agents/capabilities/
```

Semantic capability logic: booking, trip lookup, FAQ, common response/handoff.
Mỗi capability đăng ký semantic tools và reducers. Không gọi external API tại đây.

```text
src/agents/contracts/
```

Schema contract giữa Agent và Backend: `AgentInput`, `AgentAction`, `ToolCall`,
`ToolResult`, `AgentState`.

```text
src/agents/tools/
```

Tool builders, payload schemas, lifecycle helpers. Đây là schema/contract helper,
không phải nơi gọi API thật.

```text
src/agents/legacy/
```

Chỉ giữ compatibility/offline fallback. Không thêm logic production mới vào legacy.

## 4. Quy tắc tool calling

Semantic tool là cách LLM điều khiển agent.

Ví dụ đúng:

```text
User: "đón tôi ở VinUni, đến Times City, 2 người"
LLM -> update_booking(pickup_query="VinUni", destination_query="Times City", passenger_count=2)
Agent -> search_pickup / search_destination
Backend -> ToolResult
Agent -> request_vehicle_options
```

Không viết flow mới kiểu:

```python
if "đón" in text:
    ...
elif "đến" in text:
    ...
```

Chỉ dùng deterministic code cho policy an toàn, không dùng để thay LLM hiểu ngôn ngữ
tự nhiên.

Tool trong Agent là semantic tool, không phải Backend API trực tiếp. Ví dụ:

- `update_booking`;
- `search_pickup`;
- `search_destination`;
- `request_vehicle_options`;
- `request_booking_confirmation`;
- `confirm_booking`;
- `request_cancellation_confirmation`;
- `confirm_cancellation`;
- `start_rebook`;
- `lookup_trip`;
- `retrieve_knowledge`;
- `handoff`;
- `respond`.

Backend tool thật là:

- `search_place`;
- `get_vehicle_options`;
- `estimate_fare`;
- `create_booking`;
- `cancel_booking`;
- `lookup_trip`;
- `retrieve_knowledge`;
- `create_handoff`.

Agent chỉ emit backend tool qua `AgentAction(CALL_TOOL)`. Backend thực thi và trả
`ToolResult`.

## 5. Quy tắc booking

Booking là side effect. Không được tạo booking chỉ bằng câu trả lời text.

Luồng đúng:

```text
collect data
-> resolve places
-> get vehicle/fare
-> read back confirmation
-> user confirms
-> create_booking tool
-> reduce booking result
-> speak success
```

Trước `create_booking` bắt buộc có:

- pickup resolved có `place_id`;
- destination resolved có `place_id`;
- pickup khác destination;
- vehicle type;
- fare estimate id;
- phone number từ account hoặc state hợp lệ;
- `confirmation = CONFIRMED`;
- idempotency key.

Khi khách sửa thông tin:

- cập nhật field mới;
- reset dữ liệu phụ thuộc.

Ví dụ đổi destination thì phải reset:

- destination resolved cũ;
- vehicle options;
- selected vehicle;
- fare estimate;
- confirmation.

Khi khách nói “đặt lại chuyến vừa hủy”:

- không dùng lại booking id cũ;
- không dùng lại fare cũ;
- không tiếp tục chuyến đã hủy;
- tạo draft mới từ thông tin cũ bằng lifecycle transition;
- lấy lại vehicle/fare;
- xác nhận lại;
- sau đó mới `create_booking`.

## 6. Quy tắc cancellation và abandon

Phân biệt rõ:

```text
cancel booking = hủy chuyến đã tạo
abandon draft = dừng yêu cầu đang nhập, chưa có booking
```

Nếu đã có `booking_id`, muốn hủy phải qua:

```text
request_cancellation_confirmation
-> user confirms
-> confirm_cancellation
-> cancel_booking
```

Nếu chưa có `booking_id`, muốn dừng draft phải qua:

```text
request_abandon_confirmation
-> user confirms
-> confirm_abandon_booking
```

Nếu khách nói `không hủy`, `đặt xe đi`, `tiếp tục`, phải giữ draft bằng
`keep_booking` hoặc policy confirmation gate. Không được xóa draft.

## 7. Quy tắc trip lookup

Tra cứu chuyến không phải RAG.

Trip lookup phải lấy từ Booking/Trip backend:

- booking id;
- phone number từ account hoặc khách cung cấp;
- active trips;
- trip status;
- ETA.

RAG chỉ dùng cho FAQ/chính sách/dịch vụ, không dùng để trả trạng thái chuyến.

Nếu khách hỏi:

```text
còn bao lâu nữa?
```

Agent phải dùng dữ liệu chuyến hiện tại hoặc gọi `lookup_trip`. Agent không tự nhớ
hoặc tự bịa ETA.

## 8. Quy tắc FAQ/RAG

FAQ/RAG chỉ trả lời khi có tài liệu.

Luồng đúng:

```text
question
-> retrieve_knowledge
-> grounded answer with source/citation if available
```

Không trả lời chính sách, ưu đãi, phí hủy, bảo hiểm, thanh toán bằng kiến thức tự bịa.

Nếu không có tài liệu đủ tốt, nói không có thông tin chắc chắn và đề nghị hỗ trợ người
thật nếu cần.

## 9. Confirmation gates

Voice agent thường gặp lỗi “nói đã xác nhận nhưng không gọi tool”. Phải chặn lỗi này
bằng policy.

Khi state đang chờ xác nhận booking:

```text
current_step = CONFIRM
confirmation = AWAITING_CONFIRMATION
```

Các câu như:

```text
có
ừ
ok
đúng rồi
xác nhận
đặt xe đi
```

phải dẫn tới `create_booking`, không để LLM trả text như “mình đã ghi nhận”.

Khi state đang chờ xác nhận abandon/cancel, các câu phủ nhận hoặc muốn tiếp tục phải
giữ draft/booking đúng lifecycle.

## 10. Guardrail side effects

Các tool side effect:

- `create_booking`;
- `cancel_booking`;
- `create_handoff`.

Quy tắc:

- không clear pending side effect nếu chưa nhận `ToolResult` khớp `call_id`;
- replay cùng result phải idempotent;
- nếu side effect fail sau khi đã gửi request, ưu tiên reconciliation/handoff;
- không tạo side effect từ message tự do.

## 11. Không code tay thủ công theo hội thoại

Không thêm logic kiểu:

```python
if text == "1 mình":
    passenger_count = 1
if "hủy" in text:
    ...
```

trừ khi đó là policy gate cực hẹp ở trạng thái đã biết, ví dụ user đang ở
`CONFIRM` và nói `có`.

Nếu cần hiểu thêm nhiều kiểu câu, hãy:

- cập nhật instructions/tool description;
- thêm semantic tool nếu thiếu hành động;
- thêm typed state nếu thiếu dữ liệu;
- thêm reducer/policy nếu thiếu bảo vệ nghiệp vụ;
- thêm conversation eval/test.

## 12. Testing rules

Test agent theo 3 nhóm:

Tool/capability tests:

- LLM gọi semantic tool;
- capability update typed state;
- reducer xử lý `ToolResult`;
- action output đúng.

Policy/guardrail tests:

- confirmation gate;
- create/cancel booking params khớp state;
- side effect pending không bị clear;
- low STT confidence;
- rebook/cancel/abandon lifecycle.

Conversation evals:

- user nói không theo thứ tự;
- user sửa thông tin giữa chừng;
- user nói câu rác/smalltalk;
- user hỏi FAQ;
- user hỏi trạng thái chuyến;
- user đặt lại chuyến vừa hủy.

Không test bằng cách snapshot toàn bộ câu văn dài nếu không cần. Ưu tiên assert:

- action type;
- tool name;
- tool params;
- state updates;
- một vài phrase quan trọng trong message.

## 13. Khi phát hiện lỗi hội thoại

Không sửa ngay bằng một `if` mới. Trước khi sửa, phân loại lỗi:

- LLM không hiểu intent -> sửa instructions/tool descriptions hoặc thêm semantic tool;
- thiếu state -> thêm typed state field;
- stale state/lifecycle -> thêm state transition rõ;
- thiếu backend data -> yêu cầu Backend tool result/schema;
- side effect nguy hiểm -> thêm policy/guardrail;
- UI/Voice runtime -> không sửa trong Agent.

Sau đó viết test nhỏ tái hiện lỗi ở tầng đúng.

Ví dụ:

```text
Lỗi: user xác nhận nhưng agent không tạo booking.
Tầng đúng: policy confirmation gate.
Test đúng: AgentState đang CONFIRM + transcript "ừ" -> ActionType.CALL_TOOL create_booking.
```

## 14. Compatibility rules

Nếu Backend/Examples còn import path cũ, giữ wrapper mỏng trong `src/agents`:

- `src.agents.graph`;
- `src.agents.schemas`;
- `src.agents.state`;
- `src.agents.history`;
- `src.agents.location_policy`.

Wrapper chỉ re-export hoặc adapter mỏng. Không thêm business logic mới vào wrapper.

## 15. Definition of done

Một thay đổi agent chỉ được coi là xong khi:

- không phá ranh giới Agent/Backend/FE/Voice;
- LLM vẫn điều khiển hội thoại bằng semantic tools;
- business side effect được guard bằng policy;
- typed state/reducer rõ ràng;
- có test ở đúng tầng;
- `pytest tests/test_agents -q` pass;
- nếu thay contract, docs contract được cập nhật.
