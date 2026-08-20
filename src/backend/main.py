import asyncio
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure project root is available for absolute imports (src.backend.*)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- Voice AI (additive — xem docs/voice-ai/voice-runtime-architecture.md) ---
# import router riêng vào đây, không đụng src/backend/api/routes/__init__.py hay
# bất kỳ route nào đã có.
from src.backend.api.routes import health_router, router  # noqa: E402
from src.backend.api.routes.asr import router as asr_router  # noqa: E402
from src.backend.api.routes.maps import maps_router as maps_direct_router  # noqa: E402
from src.backend.api.routes.voice import prewarm_tts_cache  # noqa: E402
from src.backend.api.routes.voice import router as voice_router  # noqa: E402
from src.backend.config import get_settings  # noqa: E402
from src.voice.asr.zipformer.service import get_zipformer_service  # noqa: E402
from src.voice.config import get_voice_settings  # noqa: E402

# pytest set biến này cho mọi test đang chạy — dùng để tắt prewarm mạng thật trong
# CI/test (không dựa vào settings.app_env vì .env mặc định là "development").
_RUNNING_UNDER_PYTEST = "PYTEST_CURRENT_TEST" in os.environ


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    voice_settings = get_voice_settings()
    zipformer = get_zipformer_service()
    await zipformer.start()
    if (
        voice_settings.voice_enabled
        and settings.voice_tts_provider == "edge"
        and not _RUNNING_UNDER_PYTEST
    ):
        # Edge-only prewarm is unnecessary when OpenAI is the primary /voice/turn
        # TTS provider. Avoid the former 15-18 second HoaiMy background warmup.
        asyncio.create_task(prewarm_tts_cache())
    yield
    await zipformer.stop()
    print("Shutting down...")


app = FastAPI(
    title="AI20K Agent",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-TTS-Provider",
        "X-TTS-Voice",
        "X-TTS-Fallback",
        "X-TTS-Duration-Ms",
        "X-TTS-Review",
    ],
)

app.include_router(router, prefix="/api/v1")
app.include_router(maps_direct_router, prefix="/api")
app.include_router(health_router)
app.include_router(asr_router)

# --- Voice AI (additive) ---
voice_settings = get_voice_settings()
if voice_settings.voice_enabled:
    app.include_router(voice_router, prefix="/api/v1/voice", tags=["voice"])

    # Demo UI — cùng origin với API/WS nên không cần CORS riêng. Mount cuối cùng để
    # không che route /api/v1/* nào đã có.
    _demo_dir = PROJECT_ROOT / "demo"
    if _demo_dir.is_dir():
        app.mount("/demo", StaticFiles(directory=_demo_dir, html=True), name="demo")
