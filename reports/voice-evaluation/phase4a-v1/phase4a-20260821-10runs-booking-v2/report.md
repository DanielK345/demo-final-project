# LiveKit Phase 4 evaluation report

- Dataset: `phase4a-v1`
- Run: `phase4a-20260821-10runs-booking-v2`
- Generated: `2026-08-20T17:59:12+00:00`

## Connection smoke

- Attempts: 10
- Passed: 8
- Success rate: 0.8
- Failure stages: `{"booking_flow": 2}`

## Native LiveKit reliability

- Agent-session logs: 10
- Session transcript coverage: 0.0
- Observed speech-episode no-final rate (diagnostic only): 1.0
- Native error events: 0

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_join_after_room_ms` | 10 | 4649.66 | 4938.819 | 17568.891 | 17568.891 |
| `booking_completion_after_join_ms` | 8 | 23078.212 | 32062.755 | 32062.755 | 32062.755 |
| `booking_state_after_join_ms` | 10 | 1129.904 | 1436.289 | 1448.6 | 1448.6 |
| `credential_issue_ms` | 10 | 0.422 | 0.532 | 0.615 | 0.615 |
| `first_audio_after_join_ms` | 10 | 3029.377 | 3920.276 | 4836.506 | 4836.506 |
| `greeting_complete_after_join_ms` | 10 | 9812.24 | 12527.521 | 12674.284 | 12674.284 |
| `llm_node_ttft_ms` | 21 | 1101.72 | 1774.395 | 2125.013 | 2867.564 |
| `playback_latency_ms` | 21 | 0.315 | 0.561 | 1.449 | 2.329 |
| `room_connect_ms` | 10 | 2148.979 | 2491.229 | 2498.561 | 2498.561 |
| `room_to_worker_job_entry_ms` | 1 | 7.426 | 7.426 | 7.426 | 7.426 |
| `tool_duration_ms` | 97 | 6.35 | 10113.204 | 12631.231 | 96592.678 |
| `tts_node_ttfb_ms` | 21 | 257.488 | 266.934 | 267.948 | 274.518 |
| `worker_agent_session_built_duration_ms` | 10 | 845.089 | 1001.521 | 13777.572 | 13777.572 |
| `worker_agent_session_built_elapsed_ms` | 10 | 4104.437 | 4216.985 | 16978.839 | 16978.839 |
| `worker_greeting_requested_elapsed_ms` | 10 | 5932.154 | 6164.401 | 19188.455 | 19188.455 |
| `worker_initial_state_published_elapsed_ms` | 10 | 5931.037 | 6163.623 | 19187.451 | 19187.451 |
| `worker_job_entry_elapsed_ms` | 10 | 0.611 | 0.895 | 1.38 | 1.38 |
| `worker_job_entry_to_agent_join_ms` | 10 | 4905.896 | 5048.664 | 17903.72 | 17903.72 |
| `worker_session_start_called_elapsed_ms` | 10 | 4104.79 | 4217.246 | 16979.219 | 16979.219 |
| `worker_session_started_duration_ms` | 10 | 1585.294 | 1627.362 | 1687.779 | 1687.779 |
| `worker_session_started_elapsed_ms` | 10 | 5620.693 | 5771.008 | 18667.016 | 18667.016 |
| `worker_state_restore_completed_duration_ms` | 10 | 3177.689 | 3229.729 | 3258.437 | 3258.437 |
| `worker_state_restore_completed_elapsed_ms` | 10 | 3225.409 | 3275.855 | 3323.409 | 3323.409 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
