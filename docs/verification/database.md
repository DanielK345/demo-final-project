# Database verification

Date: **2026-08-16** · Branch: `feature/voice-ai`.

## Evidence đã chạy

| Check | Kết quả |
|---|---|
| Runtime imports | pass |
| Ruff toàn repository | pass |
| Backend/API regression | pass sau khi sửa 3 regression |
| Full offline suite | `501 passed, 2 skipped` |
| Real SQL persistence integration | pass trên SQLite/aiosqlite, không mock repository/transaction |
| Quote tamper rejection | pass |
| Idempotent booking retry | pass |
| Engine restart readback | pass cho booking, place và route snapshot |
| `alembic heads` | `0004_maps_places_routes (head)` |
| PostgreSQL `alembic current` | `0002_handoff_operations` |
| PostgreSQL connectivity | pass, credential không được in |

## Trạng thái trung thực

Code persistence và migration đã hoàn tất nhưng PostgreSQL live chưa được mutate lên head mới. Lệnh `alembic upgrade head` bị chặn vì cần phê duyệt rõ ràng cho schema/RLS mutation trên database live. Vì vậy:

- không ghi `LIVE_VALIDATED` cho migration mới;
- không chạy script acceptance trước khi DB ở đúng revision;
- giữ production readiness fail-closed;
- thao tác owner cần làm nằm trong `mustdo.md` và `docs/database_supabase.md`.

Sau khi được phê duyệt, chạy:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe scripts\verify_postgres_persistence.py
```

Chỉ cập nhật tài liệu này sang `LIVE_VALIDATED` khi lưu được output pass, timestamp, environment và người phê duyệt.
