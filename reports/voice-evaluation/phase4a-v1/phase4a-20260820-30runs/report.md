# LiveKit Phase 4 evaluation report

- Dataset: `phase4a-v1`
- Run: `phase4a-20260820-30runs`
- Generated: `2026-08-20T10:59:23+00:00`

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
| `agent_join_after_room_ms` | 30 | 4686.542 | 5356.168 | 6268.088 | 6482.36 |
| `booking_state_after_join_ms` | 30 | 1059.083 | 1258.4 | 1310.372 | 1341.316 |
| `credential_issue_ms` | 30 | 0.464 | 0.548 | 0.608 | 0.694 |
| `first_audio_after_join_ms` | 30 | 1189.009 | 1386.041 | 1414.862 | 1477.552 |
| `llm_node_ttft_ms` | 21 | 1076.152 | 1336.092 | 1378.93 | 1589.121 |
| `playback_latency_ms` | 21 | 0.344 | 0.557 | 0.583 | 0.669 |
| `room_connect_ms` | 30 | 2433.351 | 3495.052 | 3783.348 | 4711.656 |
| `tool_duration_ms` | 0 | None | None | None | None |
| `tts_node_ttfb_ms` | 21 | 246.45 | 263.218 | 271.38 | 277.592 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
