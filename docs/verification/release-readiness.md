# Release readiness matrix

Date: **2026-08-16** · Branch: `feature/voice-ai`.

| Domain | Code/test evidence | Còn thiếu | Status |
|---|---|---|---|
| PostgreSQL persistence | ORM, repositories, runtime wiring, 467-test suite và real-SQL integration pass | apply migration live, PostgreSQL acceptance, least-privilege role, backup/restore | `RELEASE_GATED` |
| Quote integrity/snapshot | stored HMAC quote, TTL, ownership, single-use, idempotency, immutable snapshots | approved production pricing/route/promotion và live PG acceptance | `STAGING_ONLY` |
| Maps/Route | fail-closed provider contract | provider, credential, service area, license | `EXTERNAL_BLOCKED` |
| Pricing | versioned catalog và deterministic engine | Finance/Product-approved AloSM catalog | `DEMO` |
| Promotion/Voucher | snapshot contract có sẵn | eligibility/ranking provider và approved budget/rules | `EXTERNAL_BLOCKED` |
| Fleet/Dispatch | booking/trip contract có sẵn | provider thật, reconciliation và SLA | `EXTERNAL_BLOCKED` |
| Auth/Consent | DB-backed auth/token/2FA/policy acceptance, encrypted sensitive field support | live migration, retention/export/delete approval | `RELEASE_GATED` |
| Agent/Handoff | typed workflow, durable state/handoff | operator queue và live transfer drill | `STAGING_ONLY` |
| Voice ASR/Rewrite/TTS | technical pipeline và automated gates | licensed model/provider, consented corpus, listening review, production soak | `RELEASE_GATED` |
| Telephony | call/WebSocket integration points | number/SIP/provider/webhook/operator destination | `EXTERNAL_BLOCKED` |
| Payment/Notification | UI/contracts only | merchant/provider/webhook/reconciliation | `EXTERNAL_BLOCKED` |
| Security/Operations | fail-closed readiness, RLS migration, no secret output | runtime DB role, advisors, pentest, DR and monitoring | `RELEASE_GATED` |

## Evidence của thay đổi này

- Ruff toàn repository: pass.
- Full non-live pytest: `501 passed, 2 skipped`.
- Real SQLite persistence/quote integration: pass, không mock repository/transaction.
- Alembic code head: `0004_maps_places_routes` (persistence/quote ở `9e9b6f420a9a`, Maps/Route nối tiếp).
- Supabase current: `0002_handoff_operations`; migration mới chưa áp dụng vì mutation live cần phê duyệt.
- PostgreSQL acceptance script: đã triển khai nhưng chưa được phép chạy trước migration.

Không domain nào được coi là `PRODUCTION_READY`. Các thao tác external/owner và expected evidence nằm trong `mustdo.md`.
