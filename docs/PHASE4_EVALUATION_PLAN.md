# Phase 4 — Voice evaluation, model benchmark và LiveKit cutover

Cập nhật: **2026-08-20** · Trạng thái: **READY TO IMPLEMENT**.

## 1. Mục tiêu

Phase 4 không viết lại pipeline. Mục tiêu là biến baseline đã test thủ công thành
bằng chứng định lượng để quyết định có chuyển runtime chính thức sang LiveKit hay
không.

Phải đánh giá đồng thời:

- streaming/session reliability;
- VAD, endpointing, turn detection và barge-in;
- ASR tiếng Việt, địa danh, accent và noise;
- conversation state/correction/confirmation;
- fallback, reconnect và handoff;
- task completion, latency và cost theo model/provider.

## 2. Baseline bị khóa trong lúc benchmark

| Stage | Baseline |
|---|---|
| Transport/session | LiveKit Room/WebRTC + local AgentServer worker |
| VAD | LiveKit Silero, fixed endpointing |
| Endpoint delay | min `0.8s`, max `2.5s` |
| Interruption | VAD, min duration `0.5s`, min words `1` |
| STT | Google `chirp_2`, `vi-VN` |
| LLM | OpenAI `gpt-4.1-mini` |
| TTS | LiveKit Inference `cartesia/sonic-3`, pinned voice, `vi` |

Không thay nhiều stage trong cùng một run. Mỗi run phải lưu config fingerprint,
model/version, timestamp, environment và dataset revision.

## 3. Trạng thái từng hạng mục

| Hạng mục | Implementation | Evaluation còn thiếu |
|---|---|---|
| Streaming/session | Đã có | reconnect, multi-tab, network loss, soak |
| VAD/turn/barge-in | Đã có và tune baseline | missed/false turn, interruption latency, noise |
| ASR tiếng Việt | Google Chirp 2 đã chạy | WER/CER/entity accuracy theo slice |
| Conversation state | Typed + durable + correction | scenario completion rate, concurrent isolation |
| Fallback | Typed failure + text fallback | failure injection và đúng recovery action |
| Handoff | Tool/record/context/UI | operator accept/join/takeover thật |
| Metrics | JSONL/raw stage metrics | aggregation p50/p95 và report |
| Model switching | ENV/provider boundary | controlled A/B trên cùng dataset |

## 4. Evaluation dataset

Dataset phải là audio có consent hoặc audio test do team tự thu; không dùng transcript
LLM sinh làm ground truth. Mỗi case cần:

- `case_id`, `dataset_version`;
- audio path/hash, duration, sample rate và noise condition;
- accent/speaker group ở mức không nhận diện cá nhân;
- expected transcript;
- expected pickup/destination entities;
- scenario steps và expected tool/state transitions;
- expected final action: ask, confirm, book, fallback hoặc handoff;
- critical tokens: phủ định, số tiền, địa chỉ, confirmation.

### Slice tối thiểu

1. Quiet, giọng Bắc/Trung/Nam.
2. Fan, traffic, café/background speech.
3. Nói nhỏ, nhanh, ngập ngừng, lặp từ và dừng giữa địa chỉ.
4. Địa danh Hà Nội dễ nhầm, tên trường, bến xe, phố, cầu và trung tâm thương mại.
5. Correction pickup/destination/vehicle nhiều lượt.
6. Barge-in lúc greeting, lúc agent hỏi và lúc đọc confirmation.
7. Empty audio, mic permission denied, disconnect và provider failure.
8. Out-of-scope, yêu cầu gặp người thật và low-confidence lặp lại.

## 5. Metrics bắt buộc

### ASR và critical entity

- WER và CER toàn tập + theo accent/noise slice.
- Exact/normalized match cho pickup và destination.
- Critical entity false-accept rate.
- Repeat-request rate.
- No-final-transcript rate.

### Turn taking

- First-turn success rate.
- Speech-start detection delay.
- End-of-turn delay.
- Missed-turn rate.
- False interruption rate.
- Barge-in detection và TTS cancellation latency.

### Business behavior

- Happy-path task completion rate.
- Correction success rate.
- Valid confirmation → booking rate.
- Booking-without-confirmation rate — bắt buộc bằng `0`.
- Duplicate booking rate khi retry/reconnect — bắt buộc bằng `0`.
- Cross-session state leakage — bắt buộc bằng `0`.
- Fallback/handoff correctness.
- Hallucinated fare/place/booking ID — bắt buộc bằng `0`.

### Latency

Ghi p50/p95 và worst case cho:

```text
speech end → final transcript
final transcript → LLM first token
tool start → tool end
LLM output → TTS first audio
speech end → user hears first audio
barge-in speech start → agent audio stopped
```

### Cost

- Google STT cost/connection time.
- OpenAI LLM input/output/cached tokens.
- LiveKit TTS characters/credits.
- LiveKit participant-minutes và data transfer.
- Cost per completed booking, không chỉ cost per request.

## 6. Test tracks

### Track A — deterministic behavioral tests

Mở rộng `tests/test_voice_agent/` bằng model/tool doubles. Kiểm tra state transition,
tool order, confirmation, invalidation, idempotency, typed failure và handoff. Track
này phải deterministic, không gọi provider live.

### Track B — offline ASR benchmark

Chạy mỗi audio qua STT candidate; lưu raw transcript, normalized transcript, timing
và provider metadata. Tính WER/CER/entity accuracy bằng script tái tạo được.

### Track C — live browser/device E2E

Ma trận tối thiểu: Chrome + Edge, laptop mic + headset + một mobile browser, quiet +
noise, normal + throttled network. Ghi call ID và JSONL tương ứng.

### Track D — provider failure/recovery

Inject timeout/unavailable/rate-limit cho STT, LLM, TTS, place, quote, persistence;
xác minh UI message, text fallback, state preservation, retry policy và handoff.

### Track E — handoff drill

Xác minh request → queue → operator accept → đúng Room/context → agent ngừng/rời theo
policy. Handoff ID ở UI chưa đủ để đóng gate này.

## 7. Model A/B

Chỉ thay một stage và dùng cùng dataset/revision:

| Run | STT | LLM | TTS | Mục đích |
|---|---|---|---|---|
| A | Google Chirp 2 | GPT-4.1 mini | Sonic 3 | Baseline hiện tại |
| B | Google Chirp 2 | Gemma 4 31B qua LiveKit | Sonic 3 | Gom LLM vào LiveKit/cost-latency |
| C | Google Chirp 2 | DeepSeek qua LiveKit nếu region cho phép | Sonic 3 | Candidate LLM khác |
| D | STT candidate | Giữ LLM A | Giữ TTS A | Chỉ khi ASR gate chưa đạt |

Không tích hợp Qwen/provider direct mới trước khi các candidate LiveKit native được
benchmark. Candidate thắng phải tốt hơn hoặc tương đương về task completion, safety,
entity accuracy và latency; giá rẻ hơn một mình không đủ.

## 8. Evidence output

Mỗi run cần tạo artifact máy đọc được và summary:

```text
reports/voice-evaluation/<dataset_version>/<run_id>/
  config.json
  environment.json
  asr-results.jsonl
  scenario-results.jsonl
  latency-summary.json
  cost-summary.json
  report.md
```

Không commit audio/PII nếu chưa có policy. Có thể commit manifest/hash và aggregate
report; audio consented lưu tại controlled storage do owner chỉ định.

## 9. Gate và quyết định cutover

Các invariant safety ở mục 5 phải bằng 0 lỗi. Ngưỡng WER/CER/entity accuracy,
completion, p50/p95 và cost phải được mentor/product/technical owner ký trước khi
chạy release evaluation; không tự bịa threshold sau khi đã xem kết quả.

Cutover chỉ khi:

- behavioral suite pass;
- ASR/turn-taking report đủ slice;
- browser/device matrix pass;
- reconnect không duplicate/cross-session leak;
- fallback và handoff E2E pass theo scope được phê duyệt;
- privacy/recording config đúng consent;
- model/cost decision được ghi rõ;
- rollback về legacy đã smoke test.

Sau cutover giữ legacy trong thời gian rollback đã chốt. Phase 5 mới xóa legacy khi
không còn caller và full tests/build pass.
