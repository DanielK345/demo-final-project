# Release readiness matrix

Date: **2026-08-16** · Branch: `feature/voice-ai` · Commit baseline: `738ea18`.

| Domain | Code | Automated test | Live validation | External dependency | Status |
|---|---|---|---|---|---|
| Database | ORM/Alembic/readiness implemented; service wiring incomplete | migration graph + readiness | Supabase `SELECT 1`, current=head | backup/PITR, retention, Redis decision | `STAGING_ONLY` |
| Maps | provider contract + fail-closed adapter | provider safety tests | no production provider | credential, service polygon, license | `EXTERNAL_BLOCKED` |
| Pricing | versioned expiring demo quote | quote safety tests | no approved pricing | Product/Finance data | `DEMO` |
| Promotion | contract documented; runtime service absent | none | none | approved rules/budget | `EXTERNAL_BLOCKED` |
| Fleet | contract documented; runtime provider absent | none | none | dispatch/fleet feed | `EXTERNAL_BLOCKED` |
| Booking | explicit confirmation/idempotency guardrails; persistence incomplete | Agent/API regressions | no dispatch provider | dispatch + approved quote source | `STAGING_ONLY` |
| RAG | grounded fallback and metadata contract | offline Agent tests | corpus not approved | Product/Legal corpus | `DEMO` |
| ASR | ZipFormer/Groq adapters, validation and benchmark tooling | Voice tests | technical artifact benchmark exists | license, consented corpus, production hardware | `RELEASE_GATED` |
| Transcript Rewrite | privacy guard + evaluator/CLI | semantic/PII hard-gate tests | prior OpenRouter canary | rotated key, data approval, real eval set | `STAGING_ONLY` |
| TTS | orchestrator, review, validation, bounded fallback | Voice/TTS tests | technical Edge-TTS report | SLA provider + two human reviewers | `RELEASE_GATED` |
| Telephony | call/websocket skeleton only | limited transport tests | none | number/SIP/webhook secret/operator destinations | `EXTERNAL_BLOCKED` |
| Handoff | typed policy/lifecycle | Agent/API/service tests | no transfer | operator queue + telephony | `STAGING_ONLY` |
| Payment | UI only | frontend build | none | merchant/webhook/reconciliation | `EXTERNAL_BLOCKED` |
| Security | secret hygiene, ownership checks, config/readiness sanitation | automated regressions | no pentest | retention/legal/pentest approval | `STAGING_ONLY` |

No row may be interpreted as `PRODUCTION_READY`; that status is intentionally not part of the project taxonomy.
## Validation result

- Full pytest: `325 passed, 5 skipped`, one dependency deprecation warning.
- Ruff and Python compile: pass.
- Alembic live: `0002_handoff_operations (head)` equals current PostgreSQL revision.
- Frontend: lint, TypeScript and Vite production build pass (`1907` modules).
- `git diff --check`: required before handoff.
