# LiveKit Phase 4 evaluation report

- Dataset: `phase4a-v1`
- Run: `phase4a-20260820-10runs-booking`
- Generated: `2026-08-20T17:18:17+00:00`

## Connection smoke

- Attempts: 10
- Passed: 7
- Success rate: 0.7
- Failure stages: `{"booking_flow": 3}`

## Native LiveKit reliability

- Agent-session logs: 10
- Session transcript coverage: 0.0
- Observed speech-episode no-final rate (diagnostic only): 1.0
- Native error events: 0

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_join_after_room_ms` | 10 | 5163.916 | 12402.692 | 25684.076 | 25684.076 |
| `booking_completion_after_join_ms` | 7 | 29738.474 | 48879.637 | 48879.637 | 48879.637 |
| `booking_state_after_join_ms` | 10 | 1873.775 | 2433.274 | 5651.872 | 5651.872 |
| `credential_issue_ms` | 10 | 0.369 | 0.644 | 0.675 | 0.675 |
| `first_audio_after_join_ms` | 10 | 4432.699 | 7573.117 | 7913.235 | 7913.235 |
| `greeting_complete_after_join_ms` | 10 | 11239.847 | 13624.138 | 15056.853 | 15056.853 |
| `llm_node_ttft_ms` | 20 | 1305.492 | 1771.175 | 2789.6 | 6320.144 |
| `playback_latency_ms` | 20 | 0.401 | 0.521 | 0.563 | 2.204 |
| `room_connect_ms` | 10 | 2093.887 | 4722.58 | 5657.911 | 5657.911 |
| `room_to_worker_job_entry_ms` | 1 | 1463.734 | 1463.734 | 1463.734 | 1463.734 |
| `tool_duration_ms` | 92 | 7.84 | 11848.259 | 18571.413 | 99590.831 |
| `tts_node_ttfb_ms` | 20 | 268.01 | 393.684 | 395.307 | 428.25 |
| `worker_agent_session_built_duration_ms` | 10 | 948.958 | 3365.044 | 19575.894 | 19575.894 |
| `worker_agent_session_built_elapsed_ms` | 10 | 4337.61 | 10899.354 | 23804.865 | 23804.865 |
| `worker_greeting_requested_elapsed_ms` | 10 | 7672.117 | 14615.942 | 27208.156 | 27208.156 |
| `worker_initial_state_published_elapsed_ms` | 10 | 7671.392 | 14615.034 | 27207.497 | 27207.497 |
| `worker_job_entry_elapsed_ms` | 10 | 0.827 | 0.953 | 1.084 | 1.084 |
| `worker_job_entry_to_agent_join_ms` | 10 | 5821.097 | 12439.165 | 26024.68 | 26024.68 |
| `worker_session_start_called_elapsed_ms` | 10 | 4337.84 | 10900.277 | 23805.613 | 23805.613 |
| `worker_session_started_duration_ms` | 10 | 2984.952 | 4545.347 | 6184.034 | 6184.034 |
| `worker_session_started_elapsed_ms` | 10 | 7151.672 | 14609.7 | 26842.505 | 26842.505 |
| `worker_state_restore_completed_duration_ms` | 10 | 3328.941 | 7566.287 | 7658.142 | 7658.142 |
| `worker_state_restore_completed_elapsed_ms` | 10 | 3388.123 | 7614.149 | 7763.796 | 7763.796 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
