# Triển khai AloSM Voice

Cập nhật: **2026-08-24** · Trạng thái: **CURRENT**

Tài liệu cũ gộp nhiều nền tảng đã được tách thành hai runbook độc lập, có đầy đủ
frontend, backend, voice worker, Supabase PostgreSQL, LiveKit Cloud và GHCR:

- [DEPLOYMENT_FLY_IO.md](DEPLOYMENT_FLY_IO.md) — triển khai toàn bộ compute lên Fly.io.
- [DEPLOYMENT_RENDER.md](DEPLOYMENT_RENDER.md) — triển khai toàn bộ compute lên Render.

Hai phương án dùng cùng kiến trúc dữ liệu và realtime:

```text
Browser -> Frontend -> HTTPS Backend -> Supabase PostgreSQL
   |                      |
   | WebRTC/WSS           | tạo JWT + explicit agent dispatch
   v                      v
LiveKit Cloud <------ Voice worker ------> Supabase PostgreSQL
                         |
                         +---- STT / LLM / TTS providers
```

LiveKit Cloud là **realtime gateway được quản lý bên ngoài**, không phải container
cần mở cổng trên Fly.io/Render. Frontend không bao giờ nhận
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, database URL hoặc khóa LLM.

## Phải đọc trước khi coi là production

Repository hiện vẫn cố ý trả `503` tại `/health/ready` khi `APP_ENV=production`
với mã `DURABLE_SERVICE_PERSISTENCE_REQUIRED`. Đây là release gate trong code,
không phải biến môi trường bị thiếu. Hai runbook dùng `/health` làm liveness để
kiểm tra hạ tầng ban đầu; không được coi việc deploy thành công là production
approval. Chỉ đổi health check sang `/health/ready` sau khi hoàn tất
[PHASE4_RELEASE_RUNBOOK.md](PHASE4_RELEASE_RUNBOOK.md), kiểm thử PostgreSQL live,
least-privilege role, multi-instance và gỡ gate bằng một thay đổi code có review.

Các file `fly.toml`, `render.yaml`, `deploy/deploy.sh`, `deploy/deploy.ps1` và
`docker-compose.prod.yml` ở root là cấu hình/luồng cũ. Không dùng chúng thay cho
hai runbook này nếu chưa đồng bộ lại command, health check và topology.

## Nguồn contract nội bộ

- [LIVEKIT_TEAM_SETUP.md](LIVEKIT_TEAM_SETUP.md)
- [database_supabase.md](database_supabase.md)
- [PHASE4_RELEASE_RUNBOOK.md](PHASE4_RELEASE_RUNBOOK.md)
- [PROJECT_SOURCE_OF_TRUTH.md](PROJECT_SOURCE_OF_TRUTH.md)
- [verification/release-readiness.md](verification/release-readiness.md)
