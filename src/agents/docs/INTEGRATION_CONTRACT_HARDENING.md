# Integration Contract Hardening

This checklist keeps Frontend, Backend, Voice, and Core Agent aligned before
refactoring the booking workflow.

## Boundary

```text
Frontend / Voice
  captures user input and displays/speaks assistant output

Backend
  owns auth, session lifecycle, state persistence, and tool execution

Core Agent
  owns dialogue decisions from trusted AgentState + AgentInput
```

No layer should silently upgrade uncertain user text into confirmed business
facts.

## Data States

| Data | Meaning | Owner |
|---|---|---|
| `transcript` | Raw user speech/text for this turn | Voice/Frontend |
| `BookingPatch` | Candidate information extracted from user text | Core Agent |
| `PlaceCandidate` | Search result returned by Backend, not yet user-confirmed if multiple | Backend tool |
| `ResolvedLocation` | Concrete place with `place_id` and customer-safe label | Backend tool + Core Agent state |
| `BookingData` | Single source of truth for booking conversation state | Core Agent state persisted by Backend |
| `ToolResult` | Backend result correlated to exactly one `ToolCall.call_id` | Backend |

## Hard Rules

1. Frontend must not auto-send marketing copy or CTA text as a user message.
   It may prefill an editable draft.
2. Backend `search_place` must return `candidates=[]` for greetings, bare
   booking intent, unsupported small talk, or garbage input.
3. Backend may only create a free-form location candidate when the text contains
   address evidence such as a number, road/building/admin unit, or known place
   token.
4. Core Agent must not call `create_booking` unless pickup and destination are
   resolved locations and confirmation is explicit.
5. `booking_progress.missing_field` must treat unresolved query text as still
   missing. Unsupported text such as a greeting must not be stored as a pickup
   or destination draft.
6. Session DTOs exposed to Frontend must accept Core Agent location shape:
   `{place_id, display_name, address}`.

## Regression Scenarios

These scenarios must stay covered by tests:

```text
User: Tôi muốn đặt xe
Agent: Bạn muốn đón ở đâu?
User: xin chào
Expected: no resolved pickup, ask for concrete pickup again
```

```text
User: Tôi muốn đặt xe
Agent: Bạn muốn đón ở đâu?
User: VinUni
Agent: Bạn muốn đi đến đâu?
User: tôi muốn đặt xe
Expected: no resolved destination, ask for concrete destination again
```

```text
Frontend CTA: AI đặt xe ngay
Expected: prefill editable text only; do not send the CTA prompt automatically
```

## Regression Gate

Keep this contract green after booking-agent changes:

```bash
.venv/bin/python -m pytest -q tests/test_backend tests/test_agents/test_agent.py
cd src/frontend && npm run build
```
