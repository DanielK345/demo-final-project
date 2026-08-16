# Agent workflow evals

Đây là bộ test **hội thoại nhiều lượt của Core Agent**, không phải test rời từng tính năng FE/BE/Voice.

## Chạy

```bash
uv run python -m eval_cases.run_agent_workflow_evals
```

Runner dùng scripted semantic decisions để kết quả tái lập được, nhưng chạy production Agent, typed state, guardrails, `SessionService` và backend tool executor thật ở chế độ in-memory. Không cần API key và không gọi mạng.

## Kết quả eval hiện tại

| Tổng số | Passed | Failed | Pytest | Overall |
|---:|---:|---:|---|---|
| 6 | 3 | 3 | 14 passed, 3 failed | `failed` |

- **Passed:** happy path (`AGENT-001`), yêu cầu ngoài phạm vi (`AGENT-005`) và handoff tổng đài viên (`AGENT-006`).
- **Failed:** đổi điểm đón (`AGENT-002`), đổi điểm đến (`AGENT-003`) và đổi loại xe (`AGENT-004`).
- **Lỗi chung:** sau khi người dùng từ chối bản xác nhận và yêu cầu sửa, Agent bỏ qua nội dung sửa, hiện lại bản xác nhận cũ và có thể tạo booking bằng dữ liệu cũ. Không có `update_booking`, `search_place` hoặc `estimate_fare` tương ứng với thay đổi của người dùng.

Chi tiết đầy đủ nằm trong [`agent_workflow_eval_summary.json`](agent_workflow_eval_summary.json).

## Cases

| ID | Flow | Evidence |
|---|---|---|
| `AGENT-001` | Happy path VinUni → Hồ Gươm | [`happy-path.json`](results/happy-path.json) |
| `AGENT-002` | Đổi điểm đón trước khi confirm | [`change-pickup.json`](results/change-pickup.json) |
| `AGENT-003` | Đổi điểm đến trước khi confirm | [`change-destination.json`](results/change-destination.json) |
| `AGENT-004` | Đổi loại xe trước khi confirm | [`change-vehicle.json`](results/change-vehicle.json) |
| `AGENT-005` | Yêu cầu ngoài phạm vi đặt xe | [`out-of-scope.json`](results/out-of-scope.json) |
| `AGENT-006` | Handoff booking dở sang tổng đài viên | [`operator-handoff.json`](results/operator-handoff.json) |

Mỗi lượt trong JSON có `user`, `assistant`, `semantic_decisions`, `backend_tools` và `state_after_turn`. File tổng hợp là [`agent_workflow_eval_summary.json`](agent_workflow_eval_summary.json).

`passed/failed` phản ánh đúng runtime hiện tại. Runner trả exit code `1` nếu Agent vi phạm expected workflow; không đổi expected output để che lỗi triển khai.
