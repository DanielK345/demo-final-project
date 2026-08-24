# LiveKit Phase 4 evaluation report

- Dataset: `manual-mic-v1`
- Run: `voice-finalization-20260821-3calls`
- Generated: `2026-08-21T13:01:22+00:00`

## Connection smoke

- Attempts: 0
- Passed: 0
- Success rate: None
- Failure stages: `{}`
- Input modes: `{}`

## Native LiveKit reliability

- Agent-session logs: 3
- Session transcript coverage: 1.0
- Observed speech-episode no-final rate (diagnostic only): 0.2647
- Native error events: 1
- Native transcription timeout events: 2

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_task_duration_ms` | 3 | 156392.293 | 204639.631 | 204639.631 | 204639.631 |
| `e2e_latency_ms` | 21 | 6246.68 | 15777.897 | 109270.479 | 162239.331 |
| `end_of_turn_delay_ms` | 24 | 1900.071 | 2377.644 | 2614.111 | 2667.131 |
| `llm_node_ttft_ms` | 28 | 1068.524 | 1753.499 | 2518.648 | 11891.23 |
| `on_user_turn_completed_delay_ms` | 25 | 0.003 | 0.005 | 0.005 | 0.01 |
| `playback_latency_ms` | 28 | 0.286 | 0.372 | 0.78 | 2.682 |
| `tool_duration_ms` | 33 | 836.186 | 2949.452 | 5460.381 | 7896.584 |
| `transcription_delay_ms` | 24 | 1897.341 | 2372.454 | 2611.282 | 2663.661 |
| `tts_node_ttfb_ms` | 28 | 262.472 | 292.038 | 300.849 | 548.853 |
| `worker_agent_session_built_duration_ms` | 3 | 13372.988 | 14186.218 | 14186.218 | 14186.218 |
| `worker_agent_session_built_elapsed_ms` | 3 | 13381.101 | 14256.482 | 14256.482 | 14256.482 |
| `worker_greeting_requested_elapsed_ms` | 3 | 17877.141 | 19609.686 | 19609.686 | 19609.686 |
| `worker_initial_state_published_elapsed_ms` | 3 | 17875.943 | 19608.238 | 19608.238 | 19608.238 |
| `worker_job_entry_elapsed_ms` | 3 | 0.655 | 4.475 | 4.475 | 4.475 |
| `worker_process_setup_status_elapsed_ms` | 3 | 0.853 | 4.882 | 4.882 | 4.882 |
| `worker_session_start_called_elapsed_ms` | 3 | 16526.348 | 17608.926 | 17608.926 | 17608.926 |
| `worker_session_started_duration_ms` | 3 | 1633.612 | 1701.438 | 1701.438 | 1701.438 |
| `worker_session_started_elapsed_ms` | 3 | 17618.127 | 19242.551 | 19242.551 | 19242.551 |
| `worker_state_restore_completed_duration_ms` | 3 | 16524.324 | 17601.053 | 17601.053 | 17601.053 |
| `worker_state_restore_completed_elapsed_ms` | 3 | 16525.836 | 17608.009 | 17608.009 | 17608.009 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
