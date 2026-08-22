# LiveKit Phase 4 evaluation report

- Dataset: `phase4a-v1`
- Run: `phase4a-20260821-1run-booking-v4-rtc114`
- Generated: `2026-08-21T07:41:42+00:00`

## Connection smoke

- Attempts: 1
- Passed: 1
- Success rate: 1.0
- Failure stages: `{}`
- Input modes: `{"livekit_text": 1}`

## Native LiveKit reliability

- Agent-session logs: 1
- STT transcript coverage: not applicable (LiveKit text-input smoke)
- Speech-episode no-final rate: not applicable (no audio input)
- Native error events: 0

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_join_after_room_ms` | 1 | 5808.925 | 5808.925 | 5808.925 | 5808.925 |
| `agent_task_duration_ms` | 1 | 48851.419 | 48851.419 | 48851.419 | 48851.419 |
| `booking_completion_after_join_ms` | 1 | 62290.226 | 62290.226 | 62290.226 | 62290.226 |
| `booking_state_after_join_ms` | 1 | 1138.339 | 1138.339 | 1138.339 | 1138.339 |
| `credential_issue_ms` | 1 | 0.391 | 0.391 | 0.391 | 0.391 |
| `first_audio_after_join_ms` | 1 | 2941.265 | 2941.265 | 2941.265 | 2941.265 |
| `greeting_complete_after_join_ms` | 1 | 11085.69 | 11085.69 | 11085.69 | 11085.69 |
| `llm_node_ttft_ms` | 5 | 1086.858 | 1463.862 | 1463.862 | 1463.862 |
| `playback_latency_ms` | 5 | 0.294 | 0.378 | 0.378 | 0.378 |
| `room_connect_ms` | 1 | 1984.624 | 1984.624 | 1984.624 | 1984.624 |
| `room_to_worker_job_entry_ms` | 1 | 228.985 | 228.985 | 228.985 | 228.985 |
| `tool_duration_ms` | 10 | 6.75 | 7.951 | 8.152 | 8.152 |
| `tts_node_ttfb_ms` | 5 | 297.063 | 459.57 | 459.57 | 459.57 |
| `worker_agent_session_built_duration_ms` | 1 | 1215.321 | 1215.321 | 1215.321 | 1215.321 |
| `worker_agent_session_built_elapsed_ms` | 1 | 1221.059 | 1221.059 | 1221.059 | 1221.059 |
| `worker_greeting_requested_elapsed_ms` | 1 | 6532.255 | 6532.255 | 6532.255 | 6532.255 |
| `worker_initial_state_published_elapsed_ms` | 1 | 6531.056 | 6531.056 | 6531.056 | 6531.056 |
| `worker_job_entry_elapsed_ms` | 1 | 0.959 | 0.959 | 0.959 | 0.959 |
| `worker_job_entry_to_agent_join_ms` | 1 | 5579.94 | 5579.94 | 5579.94 | 5579.94 |
| `worker_process_setup_status_elapsed_ms` | 1 | 1.111 | 1.111 | 1.111 | 1.111 |
| `worker_session_start_called_elapsed_ms` | 1 | 4508.818 | 4508.818 | 4508.818 | 4508.818 |
| `worker_session_started_duration_ms` | 1 | 1657.541 | 1657.541 | 1657.541 | 1657.541 |
| `worker_session_started_elapsed_ms` | 1 | 6166.377 | 6166.377 | 6166.377 | 6166.377 |
| `worker_state_restore_completed_duration_ms` | 1 | 4506.608 | 4506.608 | 4506.608 | 4506.608 |
| `worker_state_restore_completed_elapsed_ms` | 1 | 4508.321 | 4508.321 | 4508.321 | 4508.321 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
