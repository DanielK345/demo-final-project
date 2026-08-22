# LiveKit Phase 4 evaluation report

- Dataset: `phase4a-v1`
- Run: `phase4a-20260820-01`
- Generated: `2026-08-20T10:49:19+00:00`

## Connection smoke

- Attempts: 3
- Passed: 3
- Success rate: 1.0
- Failure stages: `{}`

## Native LiveKit reliability

- Agent-session logs: 3
- Session transcript coverage: None
- Observed speech-episode no-final rate (diagnostic only): None
- Native error events: 0

## Latency (milliseconds)

| Metric | Count | p50 | p90 | p95 | Worst |
|---|---:|---:|---:|---:|---:|
| `agent_join_after_room_ms` | 3 | 5479.573 | 18712.975 | 18712.975 | 18712.975 |
| `booking_state_after_join_ms` | 3 | 1077.388 | 1146.254 | 1146.254 | 1146.254 |
| `credential_issue_ms` | 3 | 0.537 | 0.643 | 0.643 | 0.643 |
| `first_audio_after_join_ms` | 3 | 1254.294 | 1340.128 | 1340.128 | 1340.128 |
| `llm_node_ttft_ms` | 1 | 1834.679 | 1834.679 | 1834.679 | 1834.679 |
| `playback_latency_ms` | 1 | 0.165 | 0.165 | 0.165 | 0.165 |
| `room_connect_ms` | 3 | 2961.945 | 3315.954 | 3315.954 | 3315.954 |
| `tool_duration_ms` | 0 | None | None | None | None |
| `tts_node_ttfb_ms` | 1 | 262.594 | 262.594 | 262.594 | 262.594 |

## Business invariants

- Passed: True
- Violations: 0

> This report aggregates native LiveKit events and structured AloSM state. It does not infer business state from transcripts.
