# LiveKit Phase 4 evaluation report

- Dataset: `phase4a-v1`
- Run: `phase4a-20260820-30runs-v2`
- Generated: `2026-08-20T15:31:55+00:00`

## Connection smoke

- Attempts: 30
- Passed: 30
- Success rate: 1.0
- Failure stages: `{}`

## Native LiveKit reliability

- Agent-session logs: 30
- Session transcript coverage: None
- Observed speech-episode no-final rate (diagnostic only): None
- Native error events: 0

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_join_after_room_ms` | 30 | 4724.303 | 6503.795 | 11642.303 | 11855.823 |
| `booking_state_after_join_ms` | 30 | 1185.791 | 1615.345 | 3386.849 | 6130.393 |
| `credential_issue_ms` | 30 | 0.528 | 0.961 | 1.304 | 1.434 |
| `first_audio_after_join_ms` | 30 | 3252.181 | 4471.771 | 8476.868 | 8549.893 |
| `greeting_complete_after_join_ms` | 30 | 10729.817 | 13909.15 | 15660.605 | 24378.266 |
| `llm_node_ttft_ms` | 30 | 1257.593 | 1979.021 | 2417.955 | 2898.906 |
| `playback_latency_ms` | 30 | 0.4 | 0.546 | 0.746 | 4.739 |
| `room_connect_ms` | 30 | 1925.595 | 3451.511 | 4585.33 | 15581.409 |
| `room_to_worker_job_entry_ms` | 4 | 419.865 | 1006.746 | 1006.746 | 1006.746 |
| `tool_duration_ms` | 0 | None | None | None | None |
| `tts_node_ttfb_ms` | 30 | 246.772 | 461.713 | 707.929 | 1221.997 |
| `worker_agent_session_built_duration_ms` | 30 | 922.882 | 1617.946 | 1750.117 | 2044.949 |
| `worker_agent_session_built_elapsed_ms` | 30 | 4095.576 | 6312.078 | 8831.498 | 22009.175 |
| `worker_greeting_requested_elapsed_ms` | 30 | 6032.492 | 9042.125 | 13748.565 | 24812.16 |
| `worker_initial_state_published_elapsed_ms` | 30 | 6031.328 | 9041.297 | 13747.619 | 24810.124 |
| `worker_job_entry_elapsed_ms` | 30 | 0.673 | 1.174 | 2.518 | 5.075 |
| `worker_job_entry_to_agent_join_ms` | 30 | 4951.816 | 7173.697 | 12171.938 | 22899.285 |
| `worker_session_start_called_elapsed_ms` | 30 | 4095.932 | 6312.384 | 8831.883 | 22009.444 |
| `worker_session_started_duration_ms` | 30 | 1485.25 | 1795.785 | 4599.717 | 7206.502 |
| `worker_session_started_elapsed_ms` | 30 | 5669.979 | 8631.59 | 13431.606 | 23669.949 |
| `worker_state_restore_completed_duration_ms` | 30 | 3117.438 | 5214.041 | 6971.057 | 20168.691 |
| `worker_state_restore_completed_elapsed_ms` | 30 | 3157.722 | 5261.231 | 7094.28 | 20258.495 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
