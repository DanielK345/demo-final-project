# LLM transcript rewrite

This document describes the post-ASR rewrite path shared by the HTTP voice API
and the LiveKit-native agent. The rewrite layer repairs transcription artifacts;
it must not infer booking facts or silently turn ambiguous speech into a command.

## Runtime flow

```text
audio
  -> streaming STT partial (UI bubble is gray)
  -> STT final (UI bubble becomes green)
  -> Agent.on_user_turn_completed
  -> deterministic aliases and booking-language repairs
  -> privacy masking
  -> LLM structured rewrite with relevant alias mappings and booking context
  -> semantic/protected-value guards
  -> final ChatMessage used by the conversation LLM
  -> rewrite result published to the UI
```

The deterministic layer runs before the model and remains available when the
provider fails or its output is rejected. Known examples include:

| ASR text | Deterministic result |
|---|---|
| `Vinyuni`, `Bin Yuni`, `Win Uni` | `VinUni` |
| `Điểm đoán là VinUni` while collecting a location | `Điểm đón là VinUni` |
| `cổng thành cũng`, `cũng chính bin Uni` during VinUni gate selection | `Cổng chính VinUni` |

The `đoán` to `đón` repair is scoped to pickup/destination collection steps. It
does not run in unrelated conversation because `đoán` is otherwise valid
Vietnamese.

## Gazetteer and alias sources

- `data/gazetteer/place_names.json`: canonical place names used as glossary.
- `data/gazetteer/hanoi_place_aliases.json`: global, exact ASR alias mappings.
- `data/gazetteer/hanoi_landmark_pickup_points.json`: candidate-specific pickup
  points and aliases, available only during an active candidate selection.

The LLM receives canonical terms plus at most six phonetic alias mappings that
are relevant to the current transcript. The entire alias catalog is never sent
on every request. Candidate names, addresses, aliases, original search query and
the last assistant selection question are included only for the active location
selection.

## Failure and timeout behavior

Rewrite is fail-open: the original transcript continues through the voice agent
when the provider is unavailable. A deterministic correction that is already
grounded in application-owned aliases is preserved even if the model times out
or returns a rejected candidate.

- Provider request timeout: `VOICE_TRANSCRIPT_REWRITE_TIMEOUT_SECONDS`.
- LiveKit hard timeout: provider timeout plus a small cancellation grace period.
- LiveKit rewrite data-channel publish timeout: one second.
- STT partial-without-final fallback: safe spoken reprompt after
  `LIVEKIT_STT_FINAL_FALLBACK_SECONDS`; partial text is not committed as user
  input because a late provider final could otherwise create a duplicate turn.

The fallback is cancelled when a final transcript arrives, a new speech turn
starts, or the session closes.

## Configuration

```dotenv
VOICE_TRANSCRIPT_REWRITE_ENABLED=true
VOICE_TRANSCRIPT_REWRITE_MODEL=gpt-4o-mini
VOICE_TRANSCRIPT_REWRITE_BASE_URL=https://api.openai.com/v1
VOICE_TRANSCRIPT_REWRITE_TIMEOUT_SECONDS=3
VOICE_TRANSCRIPT_REWRITE_REASONING_EFFORT=none
VOICE_TRANSCRIPT_REWRITE_MINIMUM_CONFIDENCE=0.85

LIVEKIT_STT_FINAL_FALLBACK_ENABLED=true
LIVEKIT_STT_FINAL_FALLBACK_SECONDS=3
```

An OpenAI base URL selects `OPENAI_API_KEY`; an OpenRouter base URL selects
`OPENROUTER_API_KEY`. Environment variables exported by the parent shell take
precedence over `.env`. LiveKit reads rewrite settings for every new job so warm
workers do not retain a stale cached `.env` view.

## Diagnostics

The JSONL `session_configured` event records:

- `transcript_rewrite_enabled`
- `transcript_rewrite_disabled_reason`: `config_disabled` or `missing_api_key`
- `transcript_rewrite_model`
- `transcript_rewrite_timeout_seconds`
- STT final fallback state and timeout

For an active rewrite, worker logs contain a bounded lifecycle:

```text
LiveKit transcript rewrite started ...
LiveKit transcript rewrite completed ...
```

or:

```text
LiveKit transcript rewrite timed out ... using raw transcript
```

`pipeline_stall stage=stt_final_missing` means STT did not finalize; the rewrite
hook has not run. `rewrite_or_commit_stalled` means STT finalized but the user
message did not reach conversation context within the watchdog threshold.

## Privacy and safety

- Phone numbers, email addresses, identifiers and numeric values are replaced
  by immutable placeholders before the provider request and restored afterward.
- Only workflow step and minimal active booking-selection context are sent.
- Model output is rejected when it changes protected placeholders, confirmation
  meaning, semantic content, or exceeds the configured confidence threshold.
- Logs contain lengths, model names, statuses and latency by default; transcript
  text requires the explicit LiveKit debug transcript opt-in.

## Verification

Relevant suites:

```bash
.venv/bin/pytest -q \
  tests/test_backend/test_transcript_rewriter_privacy.py \
  tests/test_backend/test_transcript_rewriter_config.py \
  tests/test_voice_agent/test_transcript_rewrite.py \
  tests/test_voice_agent/test_stt_final_fallback.py \
  tests/test_voice/test_gazetteer.py
```

Production acceptance should additionally use recorded, consented Vietnamese
accent/noise samples and measure entity accuracy, rewrite latency, rejection
rate, timeout rate and duplicate-turn rate.
