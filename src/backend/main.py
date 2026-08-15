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

# --- Voice AI (additive — xem docs/voice-ai/prompt_voice_integration_real_be_fe.md) ---
# import router riêng vào đây, không đụng src/backend/api/routes/__init__.py hay
# bất kỳ route nào đã có.
from src.backend.api.routes import health_router, router
from src.backend.api.routes.voice import prewarm_tts_cache
from src.backend.api.routes.voice import router as voice_router
from src.backend.config import get_settings
from src.voice.config import get_voice_settings

# pytest set biến này cho mọi test đang chạy — dùng để tắt prewarm mạng thật trong
# CI/test (không dựa vào settings.app_env vì .env mặc định là "development").
_RUNNING_UNDER_PYTEST = "PYTEST_CURRENT_TEST" in os.environ


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    voice_settings = get_voice_settings()
    if voice_settings.voice_enabled and not _RUNNING_UNDER_PYTEST:
        # QUAN TRỌNG: chạy nền (không await/không chặn startup). Prewarm gọi Edge-TTS
        # thật 3 lần tuần tự — đã tự đo mất ~15-18s. `await` trực tiếp ở đây từng khiến
        # uvicorn không bind/accept connection nào suốt khoảng thời gian đó (server có
        # vẻ "sập" từ ngoài nhìn vào, browser báo "Failed to fetch") — phát hiện thật
        # khi debug live server, xem docs/voice-ai/mustdo_voice.md.
        asyncio.create_task(prewarm_tts_cache())
    yield
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
)

app.include_router(router, prefix="/api/v1")
app.include_router(health_router)

# --- Voice AI (additive) ---
voice_settings = get_voice_settings()
if voice_settings.voice_enabled:
    app.include_router(voice_router, prefix="/api/v1/voice", tags=["voice"])

    # Demo UI — cùng origin với API/WS nên không cần CORS riêng. Mount cuối cùng để
    # không che route /api/v1/* nào đã có.
    _demo_dir = PROJECT_ROOT / "demo"
    if _demo_dir.is_dir():
        app.mount("/demo", StaticFiles(directory=_demo_dir, html=True), name="demo")
