# Repository audit — production hardening

Date: **2026-08-16** · Branch: `feature/voice-ai` · Baseline commit: `738ea18`.

## Scope and method

Scanned `src/`, `migrations/`, `tests/`, `scripts/`, `docs/` and `data/` for TODO/FIXME,
mock/fake/demo/stub, `pass`, process-memory stores, hard-coded/random/hash-generated business data
and placeholder adapters. Reference course material and test doubles were classified separately.

## Classification

| Finding | Classification | Action/evidence |
|---|---|---|
| `tests/test_voice/fake_providers.py`, `AsyncMock`, fake keys | `TEST_ONLY` | Kept; offline deterministic tests only |
| Frontend catalog/map/voucher/payment sample data | `DEMO_ALLOWED` | Remains explicitly labeled `DEMO`; never treated as API truth |
| Gazetteer names without coordinates | `DEMO_ALLOWED` | Unknown free-form text now returns unresolved/empty instead of a fabricated candidate |
| `MapsClient` returning `(0,0)` | `RUNTIME_BLOCKER` | Removed; provider-neutral contract now fails closed when unconfigured |
| Hash-generated distance/fare | `RUNTIME_BLOCKER` for production | Kept only as `DEMO`, with pricing version, expiry, `estimated=true` and `data_quality=DEMO` |
| Quote ID ignored during booking | `RUNTIME_BLOCKER` | Backend now rejects quote ID not matching route + vehicle |
| `/ready` unconditional success | `RUNTIME_BLOCKER` | Replaced by config validation + timed DB `SELECT 1` |
| Auth/session/settings/booking/trip process-memory | `RUNTIME_BLOCKER` | Not falsely marked done; typed ORM exists but runtime wiring remains code work |
| Empty Booking/Call/Event repositories | `RUNTIME_BLOCKER` | Confirmed; cannot count scaffolds as persistence |
| Handoff repository process-local | `RUNTIME_BLOCKER` | Typed lifecycle works, durable wiring still required |
| Voice provider fakes | `TEST_ONLY` | Kept; live provider gates remain separate |
| Abstract methods using `pass` in Protocol/ABC layers | `DEMO_ALLOWED` | Interface declarations, not executable stubs |
| Legacy Agent FSM/router | `HISTORICAL` | Isolated under `src/agents/legacy`; no new production work should target it |

## Priority conclusion

The database is reachable and Alembic is current, but that does not make application state durable.
The next internal P0 is wiring typed repositories for identity/session/booking/idempotency/handoff and
proving restart plus two-instance behavior. It must not be moved to `mustdo.md`.
