# LiveKit Phase 4 evaluation report

- Dataset: `phase4a-v1`
- Run: `phase4a-20260821-10runs-booking-v3`
- Generated: `2026-08-21T07:10:33+00:00`

## Connection smoke

- Attempts: 10
- Passed: 10
- Success rate: 1.0
- Failure stages: `{}`

## Native LiveKit reliability

- Agent-session logs: 10
- Session transcript coverage: 0.0
- Observed speech-episode no-final rate (diagnostic only): 1.0
- Native error events: 0

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_join_after_room_ms` | 10 | 4591.585 | 4865.425 | 17429.283 | 17429.283 |
| `booking_completion_after_join_ms` | 10 | 57613.6 | 68695.509 | 72161.019 | 72161.019 |
| `booking_state_after_join_ms` | 10 | 1184.096 | 1432.29 | 1720.881 | 1720.881 |
| `credential_issue_ms` | 10 | 0.361 | 0.708 | 0.769 | 0.769 |
| `first_audio_after_join_ms` | 10 | 2947.393 | 3352.122 | 4555.249 | 4555.249 |
| `greeting_complete_after_join_ms` | 10 | 9216.466 | 10697.923 | 12532.701 | 12532.701 |
| `llm_node_ttft_ms` | 50 | 1034.991 | 1425.519 | 1646.454 | 4661.827 |
| `playback_latency_ms` | 50 | 0.304 | 0.468 | 0.562 | 1.019 |
| `room_connect_ms` | 10 | 2092.659 | 2177.727 | 2278.455 | 2278.455 |
| `tool_duration_ms` | 110 | 5.797 | 12.697 | 46148.705 | 58291.09 |
| `tts_node_ttfb_ms` | 50 | 248.034 | 271.169 | 341.775 | 828.046 |
| `worker_agent_session_built_duration_ms` | 10 | 797.358 | 907.696 | 13322.309 | 13322.309 |
| `worker_agent_session_built_elapsed_ms` | 10 | 4001.629 | 4123.208 | 16589.457 | 16589.457 |
| `worker_greeting_requested_elapsed_ms` | 10 | 5834.673 | 6231.815 | 18660.729 | 18660.729 |
| `worker_initial_state_published_elapsed_ms` | 10 | 5833.524 | 6230.975 | 18659.55 | 18659.55 |
| `worker_job_entry_elapsed_ms` | 10 | 0.683 | 0.922 | 0.928 | 0.928 |
| `worker_job_entry_to_agent_join_ms` | 10 | 4833.678 | 4954.238 | 17680.027 | 17680.027 |
| `worker_session_start_called_elapsed_ms` | 10 | 4001.85 | 4123.552 | 16589.89 | 16589.89 |
| `worker_session_started_duration_ms` | 10 | 1512.004 | 1756.867 | 1759.973 | 1759.973 |
| `worker_session_started_elapsed_ms` | 10 | 5521.22 | 5716.279 | 18349.883 | 18349.883 |
| `worker_state_restore_completed_duration_ms` | 10 | 3138.439 | 3182.085 | 3223.1 | 3223.1 |
| `worker_state_restore_completed_elapsed_ms` | 10 | 3197.345 | 3227.381 | 3266.87 | 3266.87 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
