# LiveKit voice-flow investigation — 2026-08-21

## Focus

Diagnose delayed or missing final user transcripts in the native LiveKit voice
pipeline. Booking reliability and database persistence are tracked separately.
No VAD, endpointing, interruption, STT model, or frontend rendering behavior was
changed during this investigation.

## Runtime and native path

- `livekit-agents`: 1.6.8
- `livekit`: 1.1.14
- Turn detection: LiveKit native `vad`
- Endpointing: fixed, 0.8–2.5 seconds
- Interruption: LiveKit native `vad`
- Frontend: `useSessionMessages()` → `useTranscriptions()` using LiveKit's
  transcription text stream

This matches the documented native cascaded-agent path. Semantic/adaptive turn
detection is not part of this diagnosis.

## Evidence from real-audio logs

The automated 10-run booking batch used `livekit_text` and is excluded from the
ASR conclusions below. Existing root-level LiveKit logs contain actual
`user_input_transcribed` events and safe per-turn latency metrics.

| STT | Sessions | VAD speech episodes | Final transcripts | STT errors |
|---|---:|---:|---:|---:|
| Google `chirp_2`, `vi-VN` | 14 | 275 | 167 | 0 |
| Google `chirp_3`, `vi` | 3 | 24 | 0 | 42 |
| Google `chirp_3`, `vi-VN` | 2 | 23 | 0 | 32 |
| Deepgram `nova-3`, `vi` | 5 | 295 | 76 | 0 |

VAD speech episodes are not semantic turns, so their ratio to final transcripts
must not be treated as a no-final error rate. The explicit STT errors and native
per-turn latency metrics are stronger evidence.

For completed user turns:

| STT | Turns with metrics | Avg transcription delay | Worst | Turns over 2 s |
|---|---:|---:|---:|---:|
| Google `chirp_2` | 157 | 2.025 s | 12.853 s | 52 |
| Deepgram `nova-3` | 67 | 0.618 s | 3.362 s | 1 |

For `chirp_2`, average end-of-turn delay was 2.096 seconds and worst was 12.855
seconds, nearly identical to transcription delay. This supports the reported
behavior: the turn is waiting on the STT final result, so final transcript and
turn completion can appear late or in a burst. It does not support changing the
frontend or VAD before measuring explicit no-final events.

The old `chirp_3` sessions are a separate, conclusive provider/model failure:
five sessions emitted 74 native `STTError` events and no final transcripts.

## Native diagnostic added

LiveKit Agents 1.6.8 exposes `AgentSession(transcription_timeout=...)` and emits
`user_transcription_timeout` when VAD detects speech but no non-empty final
transcript arrives after speech ends. The application now:

- sets the native timeout to 5 seconds;
- records `user_transcription_timeout` with only speech duration and VAD start
  time (no transcript or audio content);
- includes the timeout count in aggregate reports.

This is observation only. It does not change endpointing or interruption.

## Next controlled run

Restart the worker so it loads the instrumentation, then make real microphone
calls using the existing `chirp_2`/VAD/fixed-endpointing configuration. For every
reported missing line, correlate:

1. `user_state_changed` to speaking;
2. partial/final `user_input_transcribed`;
3. `user_transcription_timeout`;
4. `conversation_item_added` for the user;
5. receipt of the LiveKit transcription stream in the browser.

Interpretation:

- timeout event present: STT final/audio-to-STT path is the problem;
- native final present but browser message absent: frontend/data-stream path;
- final present after a long delay: STT final latency/endpointing interaction;
- speech occurs only while agent is uninterruptible: interruption/audio
  withholding path documented by LiveKit.

