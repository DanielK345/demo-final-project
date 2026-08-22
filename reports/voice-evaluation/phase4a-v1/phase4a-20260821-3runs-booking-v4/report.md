# LiveKit Phase 4 evaluation report

- Dataset: `phase4a-v1`
- Run: `phase4a-20260821-3runs-booking-v4`
- Generated: `2026-08-21T07:38:06+00:00`

## Connection smoke

- Attempts: 3
- Passed: 3
- Success rate: 1.0
- Failure stages: `{}`
- Input modes: `{"livekit_text": 3}`

## Native LiveKit reliability

- Agent-session logs: 3
- STT transcript coverage: not applicable (LiveKit text-input smoke)
- Speech-episode no-final rate: not applicable (no audio input)
- Native error events: 0

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_join_after_room_ms` | 3 | 4619.796 | 5507.787 | 5507.787 | 5507.787 |
| `agent_task_duration_ms` | 3 | 49289.068 | 51263.889 | 51263.889 | 51263.889 |
| `booking_completion_after_join_ms` | 3 | 61387.616 | 65107.964 | 65107.964 | 65107.964 |
| `booking_state_after_join_ms` | 3 | 1194.924 | 1281.052 | 1281.052 | 1281.052 |
| `credential_issue_ms` | 3 | 0.489 | 0.644 | 0.644 | 0.644 |
| `first_audio_after_join_ms` | 3 | 3127.925 | 4721.273 | 4721.273 | 4721.273 |
| `greeting_complete_after_join_ms` | 3 | 9953.96 | 11822.885 | 11822.885 | 11822.885 |
| `llm_node_ttft_ms` | 15 | 1115.465 | 2912.181 | 2915.516 | 2915.516 |
| `playback_latency_ms` | 15 | 0.244 | 0.485 | 0.509 | 0.509 |
| `room_connect_ms` | 3 | 2817.749 | 3160.44 | 3160.44 | 3160.44 |
| `tool_duration_ms` | 30 | 6.756 | 10.975 | 11.531 | 12.908 |
| `tts_node_ttfb_ms` | 15 | 264.414 | 326.986 | 406.247 | 406.247 |
| `worker_agent_session_built_duration_ms` | 3 | 1199.11 | 1417.194 | 1417.194 | 1417.194 |
| `worker_agent_session_built_elapsed_ms` | 3 | 1203.147 | 1428.581 | 1428.581 | 1428.581 |
| `worker_greeting_requested_elapsed_ms` | 3 | 6003.929 | 6813.431 | 6813.431 | 6813.431 |
| `worker_initial_state_published_elapsed_ms` | 3 | 6002.66 | 6811.702 | 6811.702 | 6811.702 |
| `worker_job_entry_elapsed_ms` | 3 | 1.016 | 2.694 | 2.694 | 2.694 |
| `worker_job_entry_to_agent_join_ms` | 3 | 4868.88 | 5819.863 | 5819.863 | 5819.863 |
| `worker_process_setup_status_elapsed_ms` | 3 | 1.228 | 2.901 | 2.901 | 2.901 |
| `worker_session_start_called_elapsed_ms` | 3 | 4170.404 | 4322.996 | 4322.996 | 4322.996 |
| `worker_session_started_duration_ms` | 3 | 1519.85 | 2230.113 | 2230.113 | 2230.113 |
| `worker_session_started_elapsed_ms` | 3 | 5690.277 | 6553.163 | 6553.163 | 6553.163 |
| `worker_state_restore_completed_duration_ms` | 3 | 4167.608 | 4318.972 | 4318.972 | 4318.972 |
| `worker_state_restore_completed_elapsed_ms` | 3 | 4169.532 | 4322.486 | 4322.486 | 4322.486 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
