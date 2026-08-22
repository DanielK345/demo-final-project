# LiveKit Phase 4 evaluation report

- Dataset: `phase4-product-v1`
- Run: `phase4_run`
- Generated: `2026-08-21T11:38:11+00:00`

## Connection smoke

- Attempts: 10
- Passed: 9
- Success rate: 0.9
- Failure stages: `{"quote_confirmation": 1}`
- Input modes: `{"livekit_text": 10}`

## Native LiveKit reliability

- Agent-session logs: 10
- STT transcript coverage: not applicable (LiveKit text-input smoke)
- Speech-episode no-final rate: not applicable (no audio input)
- Native error events: 0

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_join_after_room_ms` | 10 | 5692.738 | 15041.696 | 18190.937 | 18190.937 |
| `agent_task_duration_ms` | 10 | 61902.24 | 96509.756 | 103377.889 | 103377.889 |
| `booking_completion_after_join_ms` | 9 | 74795.895 | 121490.489 | 121490.489 | 121490.489 |
| `booking_state_after_join_ms` | 10 | 1295.259 | 4967.03 | 5908.115 | 5908.115 |
| `credential_issue_ms` | 10 | 2135.731 | 6267.7 | 11556.216 | 11556.216 |
| `first_audio_after_join_ms` | 10 | 3008.818 | 8394.664 | 13986.508 | 13986.508 |
| `greeting_complete_after_join_ms` | 10 | 10601.181 | 15833.318 | 15896.125 | 15896.125 |
| `llm_node_ttft_ms` | 50 | 1073.477 | 2204.86 | 2751.368 | 3010.614 |
| `playback_latency_ms` | 50 | 0.29 | 0.424 | 0.5 | 1.055 |
| `room_connect_ms` | 10 | 2083.581 | 2775.15 | 4254.355 | 4254.355 |
| `room_to_worker_job_entry_ms` | 5 | 266.429 | 970.655 | 970.655 | 970.655 |
| `tool_duration_ms` | 97 | 965.351 | 5669.677 | 6353.903 | 17431.547 |
| `tts_node_ttfb_ms` | 50 | 278.271 | 633.832 | 1223.313 | 2982.464 |
| `worker_agent_session_built_duration_ms` | 10 | 1023.691 | 2582.266 | 5059.882 | 5059.882 |
| `worker_agent_session_built_elapsed_ms` | 10 | 1032.472 | 2591.266 | 5206.484 | 5206.484 |
| `worker_greeting_requested_elapsed_ms` | 10 | 6468.07 | 19290.039 | 20227.958 | 20227.958 |
| `worker_initial_state_published_elapsed_ms` | 10 | 6464.053 | 19289.013 | 20225.798 | 20225.798 |
| `worker_job_entry_elapsed_ms` | 10 | 0.698 | 17.126 | 18.295 | 18.295 |
| `worker_job_entry_to_agent_join_ms` | 10 | 5426.996 | 14775.267 | 17857.603 | 17857.603 |
| `worker_process_setup_status_elapsed_ms` | 10 | 0.879 | 17.412 | 18.578 | 18.578 |
| `worker_session_start_called_elapsed_ms` | 10 | 4518.295 | 9285.602 | 10039.562 | 10039.562 |
| `worker_session_started_duration_ms` | 10 | 1711.868 | 9041.294 | 9691.482 | 9691.482 |
| `worker_session_started_elapsed_ms` | 10 | 6151.534 | 18977.109 | 19080.911 | 19080.911 |
| `worker_state_restore_completed_duration_ms` | 10 | 4515.551 | 9264.911 | 10015.593 | 10015.593 |
| `worker_state_restore_completed_elapsed_ms` | 10 | 4517.338 | 9284.877 | 10039.312 | 10039.312 |

## Business invariants

- Passed: False
- Violations: 1

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
