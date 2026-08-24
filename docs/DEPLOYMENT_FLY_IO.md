# Deploy AloSM Voice lên Fly.io

Cập nhật: **2026-08-24** · Phạm vi: frontend, backend, voice worker, Supabase DB,
LiveKit Cloud realtime gateway và GHCR.

Runbook này dùng ba Fly App độc lập để backend và worker có lifecycle/scaling
riêng. Backend và worker tái sử dụng cùng một Python image; frontend dùng image
Nginx riêng.

## 1. Topology và đường kết nối

| Thành phần | Nơi chạy | Inbound | Outbound bắt buộc |
|---|---|---|---|
| Frontend React/Nginx | Fly App `FRONTEND_APP` | HTTPS 443 | Backend HTTPS |
| Backend FastAPI | Fly App `BACKEND_APP` | HTTPS 443 -> container 8000 | Supabase 5432, LiveKit HTTPS/WSS, LLM/maps provider |
| Voice worker | Fly App `WORKER_APP` | Không có public service | LiveKit WSS/HTTPS, Supabase 5432, STT/LLM/TTS |
| PostgreSQL | Supabase | TLS PostgreSQL 5432 | Không gọi ngược vào Fly |
| Realtime gateway | LiveKit Cloud | WSS/WebRTC từ browser | Dispatch job tới worker đã đăng ký |

Luồng voice hợp lệ:

1. Browser gọi backend để login/tạo session rồi gọi `POST /api/v1/livekit/prepare`
   hoặc `/api/v1/livekit/token`.
2. Backend dùng secret server-side để tạo JWT room-scoped và explicit dispatch
   cho `alosm-voice`.
3. Browser kết nối trực tiếp tới `wss://...livekit.cloud` bằng JWT ngắn hạn.
4. Worker đăng ký outbound vào cùng LiveKit project và nhận job có cùng
   `LIVEKIT_AGENT_NAME`.
5. Backend và worker đọc/ghi cùng PostgreSQL, nên state booking được khôi phục và
   đồng bộ qua LiveKit data channel.

LiveKit yêu cầu token phải được tạo ở backend vì việc tạo token cần API secret;
dispatch name phải khớp chính xác agent server. Xem
[Authentication](https://docs.livekit.io/frontends/build/authentication/) và
[Agent dispatch](https://docs.livekit.io/agents/server/agent-dispatch/).

## 2. Release gate và yêu cầu tối thiểu

Chuẩn bị:

- GitHub repository và quyền ghi package GHCR.
- Docker Buildx, `git`, `flyctl` và tài khoản Fly.io.
- Supabase project và password database.
- LiveKit Cloud project: URL dạng `wss://...`, API key, API secret.
- Provider keys/model IDs đúng với cấu hình worker.
- Tên Fly App là duy nhất toàn cầu, ví dụ `alosm-api-duy`,
  `alosm-worker-duy`, `alosm-web-duy`.

Kiểm tra local trước khi build:

```bash
git status --short
.venv/bin/python -m pytest -q
.venv/bin/python -c "import livekit.agents, yaml; print('worker dependencies: ok')"
npm --prefix src/frontend ci
npm --prefix src/frontend run build
```

Không copy `.env` vào image. `.dockerignore` đã loại `.env*`; secrets phải được
inject ở runtime bằng `fly secrets`.

## 3. Chọn tên và URL cố định

Chạy từ repository root:

```bash
export FLY_BACKEND_APP="alosm-api-<unique>"
export FLY_WORKER_APP="alosm-worker-<unique>"
export FLY_FRONTEND_APP="alosm-web-<unique>"
export FLY_REGION="sin"
export GHCR_NAMESPACE="<github-owner-lowercase>"
export GHCR_REPOSITORY="p-160"
export RELEASE_TAG="$(git rev-parse --short=12 HEAD)"

export BACKEND_PUBLIC_URL="https://${FLY_BACKEND_APP}.fly.dev"
export FRONTEND_PUBLIC_URL="https://${FLY_FRONTEND_APP}.fly.dev"
export PY_IMAGE="ghcr.io/${GHCR_NAMESPACE}/${GHCR_REPOSITORY}/backend:${RELEASE_TAG}"
export WEB_IMAGE="ghcr.io/${GHCR_NAMESPACE}/${GHCR_REPOSITORY}/frontend:${RELEASE_TAG}"
```

Tên package/image phải viết thường. Dùng tag bất biến theo Git SHA; không deploy
production từ `latest`.

## 4. Build và push image lên GHCR

### 4.1 Đăng nhập GHCR

Tạo Personal Access Token (classic) có `write:packages` và `read:packages`; nếu
organization dùng SSO thì authorize token. Không ghi token vào shell history:

```bash
read -rsp "GHCR token: " GHCR_TOKEN_VALUE
printf '%s' "$GHCR_TOKEN_VALUE" | docker login ghcr.io \
  --username "<github-user>" --password-stdin
unset GHCR_TOKEN_VALUE
```

GitHub xác nhận PAT classic dùng cho CLI, còn workflow nên dùng
`GITHUB_TOKEN`. Xem [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry).

### 4.2 Python image dùng chung cho backend và worker

```bash
docker buildx build \
  --platform linux/amd64 \
  --label "org.opencontainers.image.source=https://github.com/${GHCR_NAMESPACE}/${GHCR_REPOSITORY}" \
  --tag "$PY_IMAGE" \
  --push .

docker buildx imagetools inspect "$PY_IMAGE"
```

Root `Dockerfile` mặc định chạy FastAPI; Fly worker sẽ override command thành
production mode `python -m src.voice_agent.server start`. Không dùng `dev` trên
cloud: LiveKit mô tả `start` có graceful shutdown và production logging, còn
`dev` có auto-reload. Xem
[LiveKit startup modes](https://docs.livekit.io/agents/server/startup-modes/).

### 4.3 Frontend image

Vite bake URL vào bundle ở **build time**. Repository dùng cả `VITE_API_URL`
(auth/session/LiveKit token) và `VITE_API_BASE_URL` (maps), vì vậy truyền cùng
một backend URL cho cả hai:

```bash
docker buildx build \
  --platform linux/amd64 \
  --build-arg "VITE_API_URL=${BACKEND_PUBLIC_URL}" \
  --build-arg "VITE_API_BASE_URL=${BACKEND_PUBLIC_URL}" \
  --label "org.opencontainers.image.source=https://github.com/${GHCR_NAMESPACE}/${GHCR_REPOSITORY}" \
  --tag "$WEB_IMAGE" \
  --push src/frontend

docker buildx imagetools inspect "$WEB_IMAGE"
```

Nếu URL backend đổi, phải build lại frontend; `fly secrets set VITE_API_URL=...`
sau khi build không sửa được JavaScript bundle.

Workflow `.github/workflows/deploy.yml` cũng push tag theo full Git SHA. Trước
khi chạy workflow, tạo GitHub Actions repository variable `VITE_API_URL` bằng
`BACKEND_PUBLIC_URL`; workflow truyền giá trị này cho cả hai Vite build args.
Workflow còn chạy migration trước build, nên phải cấu hình hai Actions secrets
`DATABASE_URL` và `DATABASE_URL_MIGRATIONS` đúng endpoint trước khi dùng.

## 5. Cấu hình Supabase PostgreSQL

Trong Supabase Dashboard chọn **Connect** và copy nguyên văn connection string;
không tự đoán region/hostname.

- `DATABASE_URL`: persistent FastAPI/worker dùng Direct `:5432` nếu endpoint
  reachable qua IPv6, hoặc Shared Pooler **Session mode `:5432`**.
- `DATABASE_URL_MIGRATIONS`: Direct `:5432` ưu tiên; runner IPv4 dùng Session
  Pooler `:5432`.
- Không dùng Transaction Pooler `:6543` cho baseline long-lived này.
- Thêm `sslmode=require`; percent-encode ký tự đặc biệt trong password.

Mẫu hình dạng, không phải hostname để copy:

```text
postgresql://postgres.<PROJECT_REF>:<ENCODED_PASSWORD>@<EXACT_SESSION_POOLER_HOST>:5432/postgres?sslmode=require
postgresql://postgres:<ENCODED_PASSWORD>@db.<PROJECT_REF>.supabase.co:5432/postgres?sslmode=require
```

Supabase hiện mô tả Direct là IPv6 (trừ khi mua IPv4 add-on), Session Pooler
`:5432` dành cho persistent backend trên mạng IPv4, và Transaction `:6543` dành
cho workload tạm thời/serverless. Xem
[Connect to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres).

Chạy migration đúng một lần trước cutover:

```bash
export DATABASE_URL_MIGRATIONS="<exact-direct-or-session-5432-url>"
export DATABASE_URL="<same-runtime-5432-url>"
export QUOTE_SIGNING_KEY="<candidate-production-signing-key>"
export FIELD_ENCRYPTION_KEY="<candidate-production-encryption-key>"
.venv/bin/python -m alembic upgrade head
.venv/bin/python scripts/verify_postgres_persistence.py
unset DATABASE_URL_MIGRATIONS DATABASE_URL QUOTE_SIGNING_KEY FIELD_ENCRYPTION_KEY
```

Hai key acceptance phải là đúng hai key sẽ cấp cho backend/worker và mỗi key tối
thiểu 32 ký tự; script cố ý từ chối chạy nếu thiếu chúng.

Không chạy Alembic đồng thời trong backend và worker. Với lần đầu nên chạy từ
máy/CI đã xác nhận IPv4/IPv6; chỉ thêm Fly `release_command` sau khi đã kiểm tra
quyền migration và chiến lược rollback.

## 6. Tạo và cấu hình ba Fly App

```bash
fly auth login
fly apps create "$FLY_BACKEND_APP" --org "<fly-org>"
fly apps create "$FLY_WORKER_APP" --org "<fly-org>"
fly apps create "$FLY_FRONTEND_APP" --org "<fly-org>"
```

### 6.1 Mirror GHCR vào Fly registry

Fly chỉ pull registry ngoài trực tiếp khi image public. Để giữ GHCR private,
pull image đã tag từ GHCR rồi mirror vào registry riêng của từng Fly App:

```bash
fly auth docker

docker pull "$PY_IMAGE"
docker tag "$PY_IMAGE" "registry.fly.io/${FLY_BACKEND_APP}:${RELEASE_TAG}"
docker tag "$PY_IMAGE" "registry.fly.io/${FLY_WORKER_APP}:${RELEASE_TAG}"
docker push "registry.fly.io/${FLY_BACKEND_APP}:${RELEASE_TAG}"
docker push "registry.fly.io/${FLY_WORKER_APP}:${RELEASE_TAG}"

docker pull "$WEB_IMAGE"
docker tag "$WEB_IMAGE" "registry.fly.io/${FLY_FRONTEND_APP}:${RELEASE_TAG}"
docker push "registry.fly.io/${FLY_FRONTEND_APP}:${RELEASE_TAG}"
```

Luồng private registry này theo [Fly registry guide](https://fly.io/docs/blueprints/using-the-fly-docker-registry/).
Nếu chuyển GHCR package sang public, có thể tham chiếu trực tiếp GHCR; private
package vẫn nên mirror để không phụ thuộc credential pull của registry ngoài.

### 6.2 File cấu hình backend

Tạo file local `fly.backend.toml`:

```toml
app = "<BACKEND_APP>"
primary_region = "sin"

[processes]
  web = "sh -c 'uvicorn src.backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-1}'"

[env]
  APP_ENV = "production"
  PORT = "8000"
  LOG_LEVEL = "INFO"
  DATABASE_POOL_MODE = "auto"
  DATABASE_POOL_SIZE = "5"
  DATABASE_POOL_MAX_OVERFLOW = "5"

[http_service]
  processes = ["web"]
  internal_port = 8000
  force_https = true
  auto_start_machines = true
  auto_stop_machines = "stop"
  min_machines_running = 1

  [[http_service.checks]]
    method = "GET"
    path = "/health"
    interval = "30s"
    timeout = "5s"
    grace_period = "30s"

[[vm]]
  memory = "1gb"
  cpu_kind = "shared"
  cpus = 1
```

Thay `<BACKEND_APP>` bằng tên thật. `/health` chỉ là liveness trong giai đoạn
hạ tầng; xem release gate ở đầu tài liệu.

### 6.3 File cấu hình worker

Tạo `fly.worker.toml`; không thêm `[http_service]` và không allocate public IP:

```toml
app = "<WORKER_APP>"
primary_region = "sin"

[processes]
  worker = "python -m src.voice_agent.server start"

[env]
  APP_ENV = "production"
  LOG_LEVEL = "INFO"
  LIVEKIT_LOG_LEVEL = "INFO"
  DATABASE_POOL_MODE = "auto"
  DATABASE_POOL_SIZE = "5"
  DATABASE_POOL_MAX_OVERFLOW = "5"
  LIVEKIT_NUM_IDLE_PROCESSES = "1"

[[vm]]
  memory = "1gb"
  cpu_kind = "shared"
  cpus = 1
```

Voice jobs tạo subprocess; bắt đầu với 1 GB và theo dõi memory/exit signal trước
khi tăng idle processes hoặc concurrency.

### 6.4 File cấu hình frontend

Tạo `fly.frontend.toml`:

```toml
app = "<FRONTEND_APP>"
primary_region = "sin"

[http_service]
  internal_port = 80
  force_https = true
  auto_start_machines = true
  auto_stop_machines = "stop"
  min_machines_running = 1

[[vm]]
  memory = "256mb"
  cpu_kind = "shared"
  cpus = 1
```

## 7. Secrets và non-secret configuration

Tạo key ngẫu nhiên tối thiểu 32 bytes, ví dụ:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Backend cần:

```bash
fly secrets set -a "$FLY_BACKEND_APP" \
  DATABASE_URL="<runtime-5432-url>" \
  DATABASE_URL_MIGRATIONS="<migration-5432-url>" \
  QUOTE_SIGNING_KEY="<random-64-hex>" \
  FIELD_ENCRYPTION_KEY="<different-random-64-hex>" \
  CORS_ORIGINS="$FRONTEND_PUBLIC_URL" \
  LIVEKIT_URL="wss://<project>.livekit.cloud" \
  LIVEKIT_API_KEY="<livekit-key>" \
  LIVEKIT_API_SECRET="<livekit-secret>" \
  LIVEKIT_AGENT_NAME="alosm-voice" \
  OPENAI_API_KEY="<openai-key>"
```

Worker dùng cùng DB, LiveKit project, agent name và signing/encryption keys:

```bash
fly secrets set -a "$FLY_WORKER_APP" \
  DATABASE_URL="<same-runtime-5432-url>" \
  QUOTE_SIGNING_KEY="<same-signing-key>" \
  FIELD_ENCRYPTION_KEY="<same-encryption-key>" \
  LIVEKIT_URL="wss://<same-project>.livekit.cloud" \
  LIVEKIT_API_KEY="<same-livekit-key>" \
  LIVEKIT_API_SECRET="<same-livekit-secret>" \
  LIVEKIT_AGENT_NAME="alosm-voice" \
  LIVEKIT_STT_PROVIDER="deepgram" \
  LIVEKIT_STT_MODEL="deepgram/nova-3" \
  LIVEKIT_STT_LANGUAGE="vi" \
  LIVEKIT_LLM_PROVIDER="openai" \
  LIVEKIT_LLM_MODEL="gpt-4.1-mini" \
  LIVEKIT_TTS_PROVIDER="livekit" \
  LIVEKIT_TTS_MODEL="cartesia/sonic-3" \
  LIVEKIT_TTS_VOICE="<cartesia-voice-id>" \
  LIVEKIT_TTS_LANGUAGE="vi" \
  OPENAI_API_KEY="<same-openai-key>"
```

Model IDs thay đổi theo catalog/quota. Kiểm tra model còn tồn tại trong LiveKit
Cloud trước deploy; provider và model prefix phải khớp. Nếu Core Agent text dùng
OpenAI trực tiếp, đặt thêm `AGENT_LLM_BASE_URL=""` và model OpenAI hợp lệ. Nếu
dùng OpenRouter, đặt URL OpenRouter và `OPENROUTER_API_KEY` riêng; không dùng key
OpenRouter làm `OPENAI_API_KEY` cho speech/plugin OpenAI.

Không đặt LiveKit/DB/LLM secrets vào frontend app.

## 8. Deploy theo đúng thứ tự

```bash
fly deploy --config fly.backend.toml \
  --image "registry.fly.io/${FLY_BACKEND_APP}:${RELEASE_TAG}"

fly deploy --config fly.worker.toml \
  --image "registry.fly.io/${FLY_WORKER_APP}:${RELEASE_TAG}"

fly deploy --config fly.frontend.toml \
  --image "registry.fly.io/${FLY_FRONTEND_APP}:${RELEASE_TAG}"

fly scale count 1 -a "$FLY_BACKEND_APP" --process web
fly scale count 1 -a "$FLY_WORKER_APP" --process worker
fly scale count 1 -a "$FLY_FRONTEND_APP"
```

Không scale worker về 0: không có HTTP request để tự đánh thức worker khi
LiveKit dispatch job.

## 9. Kiểm tra kết nối end-to-end

```bash
curl -fsS "${BACKEND_PUBLIC_URL}/health"
curl -fsS "${BACKEND_PUBLIC_URL}/api/v1/status"
curl -I "${FRONTEND_PUBLIC_URL}"

fly status -a "$FLY_BACKEND_APP"
fly status -a "$FLY_WORKER_APP"
fly logs -a "$FLY_WORKER_APP"
```

Kỳ vọng log worker có `registered worker`, đúng URL project, agent name
`alosm-voice`; không có `process initialization failed`. Sau đó:

1. Mở frontend HTTPS, đăng ký/login và tạo session.
2. DevTools Network: request token đi tới `BACKEND_PUBLIC_URL`, không phải
   `localhost`; response không bị CORS.
3. Cho phép microphone và bắt đầu call.
4. LiveKit Cloud dashboard thấy room, participant browser và agent.
5. Nói một câu booking, thấy transcript/response và state UI.
6. Kiểm tra record mới trong Supabase; restart worker rồi xác nhận state khôi phục.

`/health/ready` trả `503 DURABLE_SERVICE_PERSISTENCE_REQUIRED` là expected cho
đến khi release gate được hoàn thành. Các lỗi khác như `DATABASE_UNAVAILABLE`
phải được xử lý trước cutover.

## 10. Rollback và troubleshooting

Rollback cả backend/worker về cùng SHA tương thích:

```bash
fly releases -a "$FLY_BACKEND_APP"
fly releases -a "$FLY_WORKER_APP"
fly deploy --config fly.backend.toml --image "registry.fly.io/${FLY_BACKEND_APP}:<old-sha>"
fly deploy --config fly.worker.toml --image "registry.fly.io/${FLY_WORKER_APP}:<old-sha>"
```

- Frontend gọi `localhost`: frontend được build thiếu `VITE_API_URL`; build/push
  lại image, không chỉ sửa runtime secret.
- CORS: `CORS_ORIGINS` phải là origin chính xác, không có path và không dùng `*`.
- DB `Network is unreachable` tới `db.<ref>.supabase.co`: endpoint Direct đang
  resolve IPv6; dùng exact Session Pooler `:5432` từ Dashboard hoặc IPv4 add-on.
- `ENOTFOUND` pooler: hostname bị đoán/sai region; copy lại từ Dashboard.
- Worker timeout/exit: kiểm tra RAM, provider/model, dependency và effective env;
  sau khi sửa secret phải restart/redeploy worker.
- `Application default credentials` của Google: worker thực tế đang nhận
  `LIVEKIT_STT_PROVIDER=google`; kiểm tra Fly secrets vì OS env ghi đè `.env`.
- `invalid model ID`: model không thuộc provider/catalog hiện tại.
- Có token nhưng không có agent: backend và worker khác project, khác
  `LIVEKIT_AGENT_NAME`, worker scale 0 hoặc chưa đăng ký.

Không log giá trị secret. Chỉ kiểm tra tên biến, độ dài đã redacted, hostname,
port, provider và model.
