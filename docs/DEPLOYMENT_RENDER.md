# Deploy AloSM Voice lên Render

Cập nhật: **2026-08-24** · Phạm vi: frontend, backend, voice worker, Supabase DB,
LiveKit Cloud realtime gateway và GHCR.

Runbook này dùng ba Render service:

- Web Service `alosm-backend` từ Python image.
- Background Worker `alosm-voice-worker` từ **cùng Python image** nhưng override
  start command.
- Web Service `alosm-frontend` từ Nginx image.

Supabase và LiveKit Cloud là managed external services, không tạo container
Postgres hay realtime server trên Render.

## 1. Topology và contract kết nối

| Từ | Đến | Protocol/port | Cấu hình quyết định |
|---|---|---|---|
| Browser | Frontend | HTTPS 443 | URL Render frontend |
| Frontend | Backend | HTTPS 443 | `VITE_API_URL`, `VITE_API_BASE_URL` tại build time |
| Browser | LiveKit Cloud | WSS/WebRTC | JWT do backend phát, `server_url` trong response |
| Backend | LiveKit Cloud | HTTPS/WSS outbound | `LIVEKIT_URL/API_KEY/API_SECRET` |
| Worker | LiveKit Cloud | HTTPS/WSS outbound | cùng project và `LIVEKIT_AGENT_NAME` |
| Backend + worker | Supabase | PostgreSQL TLS 5432 | cùng `DATABASE_URL` |
| Worker | STT/LLM/TTS | HTTPS/WSS outbound | provider/model/key tương ứng |

Không proxy audio qua FastAPI. Backend chỉ xác thực người dùng, tạo room-scoped
JWT và explicit dispatch; browser và worker nối trực tiếp tới LiveKit Cloud.
Frontend không được chứa LiveKit API secret, database URL hoặc provider key.

LiveKit production flow được mô tả tại
[Frontend authentication](https://docs.livekit.io/frontends/build/authentication/);
dispatch name phải khớp agent server theo
[Agent dispatch](https://docs.livekit.io/agents/server/agent-dispatch/).

## 2. Trạng thái release của repository

Với `APP_ENV=production`, `/health/ready` hiện cố ý trả `503` và
`DURABLE_SERVICE_PERSISTENCE_REQUIRED`. Gate này chỉ được gỡ bằng code change có
review sau PostgreSQL acceptance, least-privilege và multi-instance gate trong
[PHASE4_RELEASE_RUNBOOK.md](PHASE4_RELEASE_RUNBOOK.md).

Vì vậy:

- dùng `/health` làm Render health check khi dựng và smoke-test hạ tầng;
- không coi liveness pass là production approval;
- trước public cutover, hoàn thành release gate, gỡ code gate và đổi health path
  thành `/health/ready`;
- không đặt `APP_ENV=development` để giả pass production readiness.

Root `render.yaml` hiện là topology cũ: worker chạy `dev`, nhận
`DATABASE_URL` từ hostname backend và không có frontend. Không apply Blueprint
đó nguyên trạng; làm theo runbook này hoặc cập nhật Blueprint trong một PR riêng.

## 3. Yêu cầu trước khi deploy

- GitHub repository, quyền GHCR Packages và Docker Buildx.
- Tài khoản Render có Background Worker luôn chạy; free web service ngủ khi idle
  không phù hợp cho backend/voice production.
- Supabase project và database password.
- LiveKit Cloud URL/key/secret.
- STT/LLM/TTS provider models và credentials đã được xác nhận.
- Backend/worker/frontend chọn cùng Render region gần user và Supabase nhất.

Preflight local:

```bash
git status --short
.venv/bin/python -m pytest -q
.venv/bin/python -c "import livekit.agents, yaml; print('worker dependencies: ok')"
npm --prefix src/frontend ci
npm --prefix src/frontend run build
```

`.env` không được commit hoặc copy vào image. Runtime configuration đặt trong
Render Environment Groups/service environment.

## 4. Chuẩn bị tên image và release tag

```bash
export GHCR_NAMESPACE="<github-owner-lowercase>"
export GHCR_REPOSITORY="p-160"
export RELEASE_TAG="$(git rev-parse --short=12 HEAD)"
export PY_IMAGE="ghcr.io/${GHCR_NAMESPACE}/${GHCR_REPOSITORY}/backend:${RELEASE_TAG}"
export WEB_IMAGE="ghcr.io/${GHCR_NAMESPACE}/${GHCR_REPOSITORY}/frontend:${RELEASE_TAG}"
```

Luôn dùng Git SHA/semver bất biến cho deploy và rollback; `latest` chỉ là alias
tiện lợi, không phải release identity.

## 5. Push Python image lên GHCR

Tạo GitHub PAT (classic) với `write:packages`, `read:packages`; authorize SSO nếu
cần. Nhập token không echo:

```bash
read -rsp "GHCR token: " GHCR_TOKEN_VALUE
printf '%s' "$GHCR_TOKEN_VALUE" | docker login ghcr.io \
  --username "<github-user>" --password-stdin
unset GHCR_TOKEN_VALUE
```

Build image dùng chung cho backend và worker:

```bash
docker buildx build \
  --platform linux/amd64 \
  --label "org.opencontainers.image.source=https://github.com/${GHCR_NAMESPACE}/${GHCR_REPOSITORY}" \
  --tag "$PY_IMAGE" \
  --push .

docker buildx imagetools inspect "$PY_IMAGE"
```

GHCR package mặc định là private. Render hỗ trợ pull private GitHub Container
Registry bằng registry credential; không cần đổi package thành public. Xem
[Render: Deploy a prebuilt image](https://render.com/docs/deploying-an-image) và
[GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

Chưa build frontend tại đây nếu chưa biết URL backend thật. Vite bake URL API
vào JavaScript ở build time.

## 6. Tạo registry credential trên Render

Trong Render Dashboard:

1. Vào **Workspace Settings -> Container Registry Credentials**.
2. Chọn GitHub Container Registry hoặc registry `ghcr.io`.
3. Username là GitHub username; secret là PAT classic chỉ cần `read:packages`
   cho Render pull.
4. Lưu tên credential, ví dụ `ghcr-alosm-readonly`.
5. Nếu GitHub organization dùng SSO/package granular permissions, cấp package
   read access cho credential/repository tương ứng.

Không dùng PAT có `write:packages` trong Render nếu chỉ cần pull.

## 7. Cấu hình Supabase và migration

### 7.1 Chọn đúng endpoint

Trong Supabase Dashboard bấm **Connect** và copy exact connection string:

- Runtime `DATABASE_URL`: Shared Pooler **Session mode `:5432`** là lựa chọn an
  toàn cho persistent Render services trên IPv4; Direct `:5432` chỉ dùng khi đã
  xác nhận route IPv6 hoặc có IPv4 add-on.
- `DATABASE_URL_MIGRATIONS`: Direct `:5432` từ runner có IPv6; nếu GitHub
  Actions/local runner chỉ có IPv4 thì dùng exact Session Pooler `:5432`.
- Không dùng Transaction Pooler `:6543` cho backend/worker baseline.
- Thêm `sslmode=require`, URL-encode password, không đoán pooler region.

Mẫu hình dạng:

```text
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<ENCODED_PASSWORD>@<EXACT_POOLER_HOST>:5432/postgres?sslmode=require
DATABASE_URL_MIGRATIONS=postgresql://postgres:<ENCODED_PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres?sslmode=require
```

Supabase ghi rõ Direct mặc định là IPv6 và Session Pooler `:5432` dành cho
persistent backend trên IPv4. Xem
[Supabase connection methods](https://supabase.com/docs/guides/database/connecting-to-postgres).

Nếu bật Network Restrictions, phải allowlist outbound CIDR hiện hành của Render
và migration runner; restrictions áp dụng cả Direct lẫn Pooler. Xem
[Supabase Network Restrictions](https://supabase.com/docs/guides/platform/network-restrictions).

### 7.2 Chạy migration một lần

Khuyến nghị initial deploy chạy migration từ local/CI đã test network trước khi
start backend/worker:

```bash
export DATABASE_URL_MIGRATIONS="<exact-direct-or-session-5432-url>"
export DATABASE_URL="<same-runtime-url-used-by-services>"
export QUOTE_SIGNING_KEY="<candidate-production-signing-key>"
export FIELD_ENCRYPTION_KEY="<candidate-production-encryption-key>"
.venv/bin/python -m alembic upgrade head
.venv/bin/python scripts/verify_postgres_persistence.py
unset DATABASE_URL_MIGRATIONS DATABASE_URL QUOTE_SIGNING_KEY FIELD_ENCRYPTION_KEY
```

Hai key acceptance phải trùng key sẽ cấp cho backend/worker và mỗi key tối thiểu
32 ký tự; verification script cố ý từ chối chạy nếu thiếu chúng.

Không đặt `alembic upgrade head` làm start command của cả backend và worker.
Render có Pre-Deploy Command cho các paid service, nhưng nếu dùng thì chỉ cấu
hình trên backend, xác nhận migration idempotent/rollback và không lặp ở worker.

## 8. Tạo Environment Groups

Render hỗ trợ Environment Group dùng chung cho nhiều service. Tạo hai nhóm để
tránh đưa dư secret vào frontend.

### 8.1 `alosm-runtime-shared`

Link nhóm này vào backend và worker:

| Key | Giá trị |
|---|---|
| `APP_ENV` | `production` |
| `LOG_LEVEL` | `INFO` |
| `DATABASE_URL` | exact runtime Session/Direct `:5432` URL |
| `DATABASE_POOL_MODE` | `auto` |
| `DATABASE_POOL_SIZE` | `5` |
| `DATABASE_POOL_MAX_OVERFLOW` | `5` |
| `DATABASE_POOL_TIMEOUT_SECONDS` | `5` |
| `DATABASE_POOL_RECYCLE_SECONDS` | `300` |
| `QUOTE_SIGNING_KEY` | random secret tối thiểu 32 bytes |
| `FIELD_ENCRYPTION_KEY` | random secret khác, tối thiểu 32 bytes |
| `LIVEKIT_URL` | `wss://<project>.livekit.cloud` |
| `LIVEKIT_API_KEY` | LiveKit server key |
| `LIVEKIT_API_SECRET` | LiveKit server secret |
| `LIVEKIT_AGENT_NAME` | `alosm-voice` |
| `OPENAI_API_KEY` | OpenAI key nếu Core/LLM/TTS dùng OpenAI |

Tạo hai key ứng dụng:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

`DATABASE_URL_MIGRATIONS` chỉ cần ở migration runner hoặc backend pre-deploy,
không cần cấp cho worker.

### 8.2 `alosm-voice-provider`

Link chỉ vào worker:

```env
LIVEKIT_LOG_LEVEL=INFO
LIVEKIT_NUM_IDLE_PROCESSES=1
LIVEKIT_STT_PROVIDER=deepgram
LIVEKIT_STT_MODEL=deepgram/nova-3
LIVEKIT_STT_LANGUAGE=vi
LIVEKIT_LLM_PROVIDER=openai
LIVEKIT_LLM_MODEL=gpt-4.1-mini
LIVEKIT_TTS_PROVIDER=livekit
LIVEKIT_TTS_MODEL=cartesia/sonic-3
LIVEKIT_TTS_VOICE=<cartesia-voice-id>
LIVEKIT_TTS_LANGUAGE=vi
```

Đây là một cấu hình mẫu phù hợp với source hiện tại, không phải bảo đảm model
còn được account cấp quyền. Kiểm tra model catalog/quota trước deploy. Provider
và model phải khớp; nếu chọn Google STT thì cần Google credentials/project đúng.
Khi không dùng Google, effective env phải là `LIVEKIT_STT_PROVIDER=deepgram`.

Nếu Core Agent text gọi OpenAI trực tiếp, trên backend và worker đặt:

```env
AGENT_LLM_ENABLED=true
AGENT_LLM_BASE_URL=
AGENT_LLM_MODEL=gpt-4.1-mini
```

Nếu dùng OpenRouter, dùng URL/key riêng; không thay thế `OPENAI_API_KEY` bằng
OpenRouter key cho plugin speech/OpenAI.

Render docs cho phép share secrets qua Environment Groups:
[Environment variables and secrets](https://render.com/docs/configure-environment-variables).

## 9. Tạo Backend Web Service

Trong Dashboard chọn **New -> Web Service -> Existing Image**:

| Setting | Giá trị |
|---|---|
| Name | `alosm-backend` hoặc tên unique |
| Image | giá trị đầy đủ của `PY_IMAGE` |
| Registry credential | `ghcr-alosm-readonly` |
| Region | cùng region với worker, gần Supabase/user |
| Instance | paid/always-on cho production |
| Environment Group | `alosm-runtime-shared` |
| Health Check Path | `/health` trong giai đoạn release gate |
| `PORT` | `10000` hoặc để Render default |
| `CORS_ORIGINS` | tạm đặt URL frontend dự kiến, sửa thành URL thật ở bước 12 |

Root image đã bind FastAPI vào `0.0.0.0:${PORT:-8000}`. Nếu dashboard yêu cầu
Docker Command, dùng:

```text
sh -c 'uvicorn src.backend.main:app --host 0.0.0.0 --port ${PORT:-10000} --workers ${WEB_CONCURRENCY:-1}'
```

Render yêu cầu web service bind `0.0.0.0` và khuyến nghị `$PORT` (mặc định
10000). Xem [Render Web Services](https://render.com/docs/web-services/).

Deploy và ghi lại URL thật, ví dụ:

```bash
export RENDER_BACKEND_URL="https://alosm-backend-xxxx.onrender.com"
```

Kiểm tra:

```bash
curl -fsS "${RENDER_BACKEND_URL}/health"
curl -fsS "${RENDER_BACKEND_URL}/api/v1/status"
```

Không dùng `/health/ready` làm health path trước khi release gate đã được gỡ;
Render coi 4xx/5xx là unhealthy và có thể hủy/restart deploy. Xem
[Render Health Checks](https://render.com/docs/health-checks).

## 10. Build/push Frontend image với URL backend thật

Repository frontend đọc hai biến build-time. Truyền cùng URL backend:

```bash
docker buildx build \
  --platform linux/amd64 \
  --build-arg "VITE_API_URL=${RENDER_BACKEND_URL}" \
  --build-arg "VITE_API_BASE_URL=${RENDER_BACKEND_URL}" \
  --label "org.opencontainers.image.source=https://github.com/${GHCR_NAMESPACE}/${GHCR_REPOSITORY}" \
  --tag "$WEB_IMAGE" \
  --push src/frontend

docker buildx imagetools inspect "$WEB_IMAGE"
```

Runtime env trên Render không thể thay giá trị đã bake vào Vite bundle. Mỗi khi
backend origin đổi, build và push frontend tag mới.

Nếu dùng `.github/workflows/deploy.yml`, tạo GitHub Actions repository variable
`VITE_API_URL` bằng `RENDER_BACKEND_URL`. Workflow push full Git SHA cho backend
và frontend, đồng thời chạy migration trước build; vì vậy phải cấu hình Actions
secrets `DATABASE_URL` và `DATABASE_URL_MIGRATIONS` trước khi kích hoạt.

## 11. Tạo Voice Background Worker

Chọn **New -> Background Worker -> Existing Image**:

| Setting | Giá trị |
|---|---|
| Name | `alosm-voice-worker` |
| Image | cùng exact `PY_IMAGE`/SHA với backend |
| Registry credential | `ghcr-alosm-readonly` |
| Region | cùng region backend |
| Instance | always-on, khởi đầu ít nhất 1 GB RAM |
| Environment Groups | `alosm-runtime-shared`, `alosm-voice-provider` |
| Docker Command | `python -m src.voice_agent.server start` |

Background Worker không có URL/health endpoint và chỉ cần outbound network.
Không tạo Web Service giả cho worker. Render mô tả worker là process chạy liên
tục, không expose hostname nhưng có thể gọi outbound:
[Service types](https://render.com/docs/service-types).

Kỳ vọng log:

```text
registered worker ... agent_name=alosm-voice ... url=wss://...livekit.cloud
```

Không dùng `python -m src.voice_agent.server dev`; LiveKit khuyến nghị `start`
cho production vì có graceful shutdown và optimized logging:
[Server options](https://docs.livekit.io/agents/server/options/).

## 12. Tạo Frontend Web Service

Chọn **New -> Web Service -> Existing Image**:

| Setting | Giá trị |
|---|---|
| Name | `alosm-frontend` |
| Image | exact `WEB_IMAGE`/SHA vừa build |
| Registry credential | `ghcr-alosm-readonly` |
| Region | cùng region backend |
| Instance | theo traffic |
| `PORT` | `80` |
| Health Check Path | `/` |

Nginx image hiện listen `0.0.0.0:80`; Render thường tự detect cổng khác 10000,
nhưng đặt `PORT=80` làm expected port rõ ràng. Không đặt runtime secrets vào
frontend.

Sau deploy ghi lại URL:

```bash
export RENDER_FRONTEND_URL="https://alosm-frontend-xxxx.onrender.com"
curl -I "$RENDER_FRONTEND_URL"
```

Quay lại Backend -> Environment và đặt chính xác:

```env
CORS_ORIGINS=https://alosm-frontend-xxxx.onrender.com
```

Không có dấu `/` cuối, không có path, không dùng `*`. Render sẽ redeploy backend
sau thay đổi env.

## 13. Thứ tự deploy/redeploy chuẩn

Initial deployment:

1. Push Python image GHCR.
2. Chạy Alembic + persistence verification một lần.
3. Tạo env groups và backend.
4. Lấy backend URL thật.
5. Build/push frontend image với URL đó.
6. Tạo worker từ cùng Python SHA.
7. Tạo frontend từ frontend SHA.
8. Cập nhật backend `CORS_ORIGINS` bằng frontend URL thật.
9. Smoke test end-to-end.

Release sau đó:

1. Tests pass.
2. Build/push hai image với SHA mới; frontend vẫn bake backend stable URL.
3. Migration một lần nếu release có migration.
4. Redeploy backend và worker từ **cùng Python SHA**.
5. Redeploy frontend SHA mới.
6. Smoke test; chỉ sau đó mới promote/cutover.

Image-backed Render services không auto-deploy chỉ vì GHCR có tag mới. Dùng
Manual Deploy/API/deploy hook có kiểm soát; không mutate `latest` rồi giả định
service tự cập nhật. Render nêu rõ behavior này trong
[prebuilt image guide](https://render.com/docs/deploying-an-image).

## 14. End-to-end smoke test

### 14.1 HTTP và effective public config

```bash
curl -fsS "${RENDER_BACKEND_URL}/health"
curl -fsS "${RENDER_BACKEND_URL}/api/v1/status"
curl -I "${RENDER_FRONTEND_URL}"
```

`/api/v1/status` phải báo `livekit_configured: true` và agent name
`alosm-voice`; endpoint chỉ hiển thị metadata an toàn, không secret.

### 14.2 Browser/LiveKit/DB

1. Mở frontend HTTPS, login và tạo application session.
2. DevTools Network xác nhận các request `/api/v1/...` đi tới Render backend,
   không phải `localhost` hay frontend origin.
3. Request LiveKit token/prepare trả 201; không có CORS/401 ngoài expected auth.
4. Cho phép microphone, bắt đầu call.
5. LiveKit Cloud dashboard thấy browser participant và agent participant.
6. Worker log có job/session start, STT/LLM/TTS không lỗi provider/model.
7. State booking hiển thị qua data channel và record tồn tại trong Supabase.
8. Restart worker; tạo/resume call và xác nhận durable state hoạt động.

`/health/ready` còn trả `DURABLE_SERVICE_PERSISTENCE_REQUIRED` cho tới khi
release gate code được hoàn tất. `DATABASE_UNAVAILABLE` hoặc provider failures
không phải expected và phải sửa.

## 15. Connection budget và scaling

Mỗi backend/worker instance mặc định có pool size 5 và overflow 5. Trước khi
scale, tính upper bound:

```text
(backend instances + worker instances) * (pool_size + max_overflow)
```

Giữ tổng thấp hơn connection budget của Supabase và chừa headroom cho migration,
Dashboard và ops. Worker LiveKit spawn subprocess per job; scale RAM/concurrency
từ metrics thực, không chỉ từ số HTTP request.

Backend và worker phải cùng schema/image-compatible version. Không deploy schema
breaking migration trước khi old instances đã drain hoặc code hỗ trợ cả hai
schema.

## 16. Rollback

1. Trong Render service, chọn image tag/digest SHA cũ.
2. Rollback backend và worker cùng compatible Python SHA.
3. Rollback frontend nếu API contract/assets liên quan.
4. Không tự downgrade DB; dùng migration rollback plan đã review hoặc forward fix.
5. Chạy lại HTTP + voice + persistence smoke test.

GHCR hỗ trợ pull theo digest; pin digest là lựa chọn mạnh nhất để bảo đảm artifact
không thay đổi.

## 17. Troubleshooting theo triệu chứng

- **Frontend gọi `http://localhost:8000`**: frontend image build thiếu
  `VITE_API_URL`; build/push tag mới với cả hai build args rồi redeploy.
- **Maps gọi sai origin nhưng auth đúng**: thiếu `VITE_API_BASE_URL`.
- **CORS**: `CORS_ORIGINS` backend không khớp exact frontend origin; sửa và
  redeploy backend.
- **DB báo IPv6 `Network is unreachable`**: đang dùng Direct endpoint trên
  network không route IPv6; chuyển sang exact Session Pooler `:5432` hoặc IPv4
  add-on.
- **Pooler `ENOTFOUND`/auth failed**: không đoán hostname/user; copy lại toàn bộ
  URL từ Supabase Dashboard, encode password.
- **Worker nhận host của backend làm DB URL**: cấu hình sai kiểu Blueprint cũ;
  backend hostname không phải PostgreSQL. Link cùng Environment Group có DSN
  Supabase thật vào cả hai service.
- **Worker init timeout/exit non-zero**: kiểm tra memory, package trong image,
  provider/model và effective environment; redeploy/restart sau khi sửa env.
- **Worker yêu cầu Google credentials dù muốn Deepgram**: OS env của Render đang
  là `LIVEKIT_STT_PROVIDER=google`; environment platform ghi đè `.env` trong
  image. Sửa env group/service override.
- **`invalid model ID`**: provider/model prefix không khớp hoặc model/quota không
  còn khả dụng.
- **Token tạo được nhưng agent không join**: worker chưa `registered`, khác
  LiveKit project, khác `LIVEKIT_AGENT_NAME`, hoặc worker bị suspend.
- **Render deploy web fail vì port**: backend phải bind `0.0.0.0:$PORT`; frontend
  Nginx listen 80 và service đặt expected `PORT=80`.
- **Health check loop**: trong giai đoạn hiện tại dùng `/health`, không dùng
  `/health/ready` để che release gate; xử lý gate đúng quy trình trước cutover.

Khi debug chỉ in metadata đã redacted: tên biến tồn tại, hostname/port,
provider/model, độ dài key. Không in DSN password, API key hoặc secret.
