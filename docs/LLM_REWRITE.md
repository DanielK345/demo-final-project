# LLM transcript rewrite

This document describes the post-ASR rewrite path shared by the HTTP voice API
and the LiveKit-native agent. The rewrite layer repairs transcription artifacts;
it must not infer booking facts or silently turn ambiguous speech into a command.

## Runtime flow

```text
audio
  -> streaming STT partial (UI bubble is gray)
  -> STT provider final fragments remain gray
  -> 2 seconds of silence closes one logical user turn
  -> Agent.on_user_turn_completed
  -> deterministic aliases and booking-language repairs
  -> privacy masking
  -> LLM structured rewrite with relevant alias mappings and booking context
  -> semantic/protected-value guards
  -> final ChatMessage used by the conversation LLM
  -> rewrite result published to the UI (the coalesced bubble becomes green)
```

LiveKit preemptive generation is disabled for this pipeline. The conversation
LLM and TTS therefore cannot start from a partial transcript while the rewrite
hook is still pending. Provider-final fragments separated by less than two
seconds are accumulated into the same turn; the frontend coalesces the matching
fragments into one gray bubble and replaces its text with `normalized_text`
when the rewrite result arrives. This prevents two adjacent user bubbles from
representing one interrupted utterance.

The deterministic layer runs before the model and remains available when the
provider fails or its output is rejected. Known examples include:

| ASR text | Deterministic result |
|---|---|
| `Vinyuni`, `Bin Yuni`, `Bin Unite`, `biên Uni`, `Win Uni` | `VinUni` |
| `Điểm đoán là VinUni` while collecting a location | `Điểm đón là VinUni` |
| `cổng thành cũng`, `cũng chính bin Uni` during VinUni gate selection | `Cổng chính VinUni` |
| `cũng chính`, `cũng phụ`, `cũng trước`, `cũng sau`, `cũng số 2` | corresponding `cổng ...` phrase |

The `đoán` to `đón` repair is scoped to pickup/destination collection steps. It
does not run in unrelated conversation because `đoán` is otherwise valid
Vietnamese.

The `cũng` to `cổng` repair is deterministic before the LLM whenever `cũng` is
followed by a gate qualifier (`chính`, `phụ`, `trước`, `sau`), a gate number or
a context-known gate/place name. It also runs when the booking is already
complete and the user is correcting a locked location.

## Gazetteer and alias sources

- `data/gazetteer/place_names.json`: canonical place names used as glossary.
- `data/gazetteer/hanoi_place_aliases.json`: global, exact ASR alias mappings.
- `data/gazetteer/hanoi_landmark_pickup_points.json`: candidate-specific pickup
  points and aliases, available only during an active candidate selection.

The LLM receives canonical terms plus at most six phonetic alias mappings that
are relevant to the current transcript. The exact pickup and destination names
already selected in booking state are placed first in the canonical terms and
sent as `known_booking_places`; this is the same canonical state displayed in
the confirmation panel. The entire alias catalog is never sent on every
request. Candidate names, addresses, aliases, original search query and the last
assistant selection question are included only for the active location
selection.

## Bounded rewrite memory

Each rewrite request uses three complementary memory sources:

- authoritative `locked_booking_slots` projected from `BookingDraft`;
- a privacy-redacted short dialogue window, bounded by
  `VOICE_TRANSCRIPT_REWRITE_CONTEXT_WINDOW_TURNS`;
- ASR confusion memory combining the gazetteer, relevant place aliases, the
  curated Vietnamese patterns in
  `data/gazetteer/vietnamese_asr_confusions.json`, and recent accepted
  corrections from this call.

The call-local correction list is bounded by
`VOICE_TRANSCRIPT_REWRITE_MEMORY_MAX_CORRECTIONS`. It is intentionally excluded
from durable voice state, so enabling this feature does not silently enable
transcript retention. Phone numbers, emails, IDs and numeric text in the short
dialogue window are redacted before the provider request.

Deterministic corrections run before the confidence gate and again after model
output. Consequently, a low-confidence turn can still receive a uniquely
grounded alias correction, and the model cannot reintroduce a known typo before
the normalized result is published to the green user bubble.

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
VOICE_TRANSCRIPT_REWRITE_CONTEXT_WINDOW_TURNS=3
VOICE_TRANSCRIPT_REWRITE_MEMORY_MAX_CORRECTIONS=6

LIVEKIT_STT_FINAL_FALLBACK_ENABLED=true
LIVEKIT_STT_FINAL_FALLBACK_SECONDS=3
LIVEKIT_ENDPOINTING_MODE=fixed
LIVEKIT_ENDPOINTING_MIN_DELAY_SECONDS=2.0
LIVEKIT_ENDPOINTING_MAX_DELAY_SECONDS=3.0
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
- `transcript_rewrite_context_window_turns`
- `transcript_rewrite_memory_max_corrections`
- endpointing min/max delay and `preemptive_generation_enabled=false`
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
- Only bounded, redacted dialogue plus minimal authoritative booking context are sent.
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
