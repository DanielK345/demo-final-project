# Phase 4 product — 10-run investigation

Generated from the ten `app_session_id` values in `connection-results.jsonl` and
their matching native LiveKit logs. Retry logs are excluded from aggregate
percentiles and discussed separately below.

## Decision

The release gate is not met: 9/10 attempts passed and run 4 failed. The first
fix target is database-backed session restoration and the behavior used when
restoration times out. There is no evidence in this batch that justifies an
ASR, VAD, endpointing, or frontend-transcript change.

## Gate result

- Attempts: 10
- Passed: 9
- Failed: 1 (`quote_confirmation`, `TimeoutError`)
- Business-invariant violations: 1 (`durable_booking_verification_failed`, run 4)
- Input mode: `livekit_text` for all 10 attempts
- Native event logs included in the aggregate: 10

## Startup evidence

| Metric | p50 | p90 | p95/worst |
|---|---:|---:|---:|
| Credential preparation | 2.136 s | 6.268 s | 11.556 s |
| Room connection | 2.084 s | 2.775 s | 4.254 s |
| Agent join after room | 5.693 s | 15.042 s | 18.191 s |
| State restore | 4.516 s | 9.265 s | 10.016 s |
| Session start | 1.712 s | 9.041 s | 9.691 s |
| First audio after join | 3.009 s | 8.395 s | 13.987 s |

Runs 1, 2, and 4 are the startup outliers. Run 4 spent 10.016 seconds in state
restore and joined 15.042 seconds after the Room connected. State restore and
session start, rather than TTS alone, dominate these outliers. Credential
preparation also has a real outlier in this batch, so it cannot be excluded
without splitting durable-session creation, database checkout, and token
signing into separate timings.

The effective runtime database configuration points to the direct Supabase
Postgres hostname on port 5432 with a bounded SQLAlchemy pool (`pool_size=5`,
`max_overflow=5`, `pool_timeout=5s`, `pool_recycle=300s`, pre-ping enabled).
The LiveKit job process still pays a cold database checkout/query cost before
the first useful turn. Raising the restore timeout alone would hide the symptom
and extend join latency; connect, checkout, pre-ping, and query time need to be
measured separately before changing the timeout or endpoint.

## Persistence failure chain

Run 4 and its first two retries all crossed the restore-timeout region and
started the voice flow with persistence disabled:

| Attempt | Restore | Persistence | Result |
|---|---:|---|---|
| Main run 4 | 10.016 s | disabled | quote confirmation timeout; no booking |
| Retry 1 | 11.136 s | disabled | quote confirmation timeout; no booking |
| Retry 2 | 13.786 s | disabled | booking created; durable session verification failed |
| Retry 3 | 14.647 s | enabled | destination-selection timeout |

A read-only database check after the run found the first three session rows
still `ACTIVE`, with no session-level booking and `voice_state_revision=0`.
Retry 2 nevertheless had matching durable quote and booking rows. This is
consistent with the current architecture: quote/booking services write through
their own repositories, while `DatabaseVoiceStateStore.save()` becomes a no-op
when persistence is disabled. The resulting partial success is precisely why
the durable session gate failed (`session_ended=false`,
`session_booking_matches=false`, `state_advanced=false`).

The runtime log shows the failed main run attempted `estimate_fare` twice (4.518
seconds and 2.568 seconds) and the enclosing `start_booking` AgentTask ended in
error after 79.003 seconds. `start_booking` duration is the whole multi-turn
AgentTask, not a single backend database call.

There is also source/runtime drift to resolve before another release run. The
focused test `test_state_restore_timeout_falls_back_without_blocking_voice_session`
expects a timeout to set `persistence_enabled=false`, and the captured runtime
logs show that behavior. The current `restore_session_data()` implementation
does not set the flag, so that test fails. Either the worker ran an older source
revision or the workspace contains an incomplete change. Do not tune production
behavior until implementation, test contract, and deployed worker revision are
made consistent.

## Transcript/ASR evidence

This batch cannot measure missing spoken transcripts:

- all attempts used `livekit_text`;
- debug logs were created with transcript content disabled;
- synthetic text turns produce near-instant user speaking/listening transitions;
- there was no controlled microphone audio manifest or expected transcript.

Therefore `final_transcripts=0` and the raw speech-episode diagnostic must not be
interpreted as ASR failure. The aggregate report correctly marks STT transcript
coverage and no-final rate as not applicable.

## Fix order

1. **P0 — align runtime and source contract.** Record the exact worker commit or
   source hash, then make timeout behavior and its focused test agree.
2. **P0 — fail safely when persistence is unavailable.** A booking flow must not
   create quote/booking rows while session persistence is disabled. Either retry
   restoration before the first mutation or reject/handoff the booking flow with
   an explicit unavailable state. Do not silently continue with a no-op store.
3. **P0 — instrument database startup.** Add privacy-safe timings for pool
   checkout/connect, pre-ping, restore SELECT, and restore outcome/exception.
   Compare direct Postgres with the supported session-pooler endpoint using the
   same 10-run protocol; keep only one variable changed.
4. **P1 — inspect quote and booking writes.** Add operation-level timings and
   typed failure codes around pricing-catalog lookup, quote insert, state save,
   booking insert, and terminal session update. The native tool status alone
   does not expose the underlying exception.
5. **Rerun the durable booking gate.** Require 10/10, all six `durable_*` checks,
   no persistence-disabled session, and no source/runtime drift.
6. **Run a separate real-audio test.** Use controlled/consented audio or the
   browser/device matrix, enable privacy-safe final-transcript event logging,
   and correlate audio/VAD, STT final, native transcript event, and frontend
   render. Only then consider ASR/VAD/endpointing changes.

## Generated artifacts

- `report.md`
- `latency-summary.json`
- `failure-summary.json`
- `business-invariants.json`
- `config.json`
- `environment.json`
- `cost-summary.json`

