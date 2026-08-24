"""Standalone Zipformer Streaming ASR Server — FastAPI + WebSocket.

Protocol (see docs/VOICE_ARCHITECTURE.md for full spec):
  WS /v1/stt  — PCM16 streaming ASR
  GET /health  — liveness + model status
  GET /ready   — readiness gate (503 until model loaded)
  GET /metrics — Prometheus text metrics
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import numpy as np
from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .config import ASRServerSettings, get_asr_server_settings
from .recognizer import RecognizerPool

logger = logging.getLogger(__name__)
_pool: RecognizerPool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    settings = get_asr_server_settings()
    logging.basicConfig(level=logging.INFO)
    logger.info("ASR server starting model_dir=%s", settings.zipformer_model_dir)
    _pool = RecognizerPool(settings)
    try:
        await asyncio.to_thread(_pool.load)
        logger.info("ASR model ready")
    except Exception as exc:
        logger.error("ASR model load FAILED: %s", exc)
        if settings.asr_required:
            raise
    yield
    if _pool:
        _pool.shutdown()
    logger.info("ASR server stopped")


def create_app() -> FastAPI:
    s = get_asr_server_settings()
    app = FastAPI(title="AloSM ASR Server", version="1.0.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins_list,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, Any]:
        ready = _pool is not None and _pool.ready
        return {
            "status": "ok" if ready else "loading",
            "model_loaded": ready,
            "model": s.asr_model_id,
            "provider": s.sherpa_provider,
            "chunk_size": s.asr_chunk_size,
            "active_sessions": _pool.active_count if _pool else 0,
        }

    @app.get("/ready")
    async def readiness():
        if _pool is None or not _pool.ready:
            return Response(status_code=503, content=b"model not ready")
        return {"ready": True}

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics():
        return _pool.prometheus_metrics() if _pool else "# not loaded\n"

    @app.websocket("/v1/stt")
    async def stt_ws(ws: WebSocket):  # noqa: C901
        await ws.accept()
        sid = f"asr-{int(time.time() * 1000)}"
        logger.info("ws_connect sid=%s", sid)

        if _pool is None or not _pool.ready:
            await ws.send_text(json.dumps({"type": "error", "code": "MODEL_UNAVAILABLE"}))
            await ws.close(1013)
            return

        # 1. Handshake
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=s.ws_handshake_timeout)
            msg = json.loads(raw)
            if msg.get("type") != "start":
                await ws.send_text(json.dumps({"type": "error", "code": "PROTOCOL_ERROR"}))
                await ws.close(1002)
                return
            client_sr = int(msg.get("sample_rate", 16000))
        except Exception as exc:
            logger.warning("ws_handshake_fail sid=%s: %s", sid, exc)
            await ws.close(1002)
            return

        # 2. Acquire recognizer
        recognizer = _pool.acquire()
        if recognizer is None:
            await ws.send_text(json.dumps({"type": "error", "code": "CAPACITY"}))
            await ws.close(1013)
            return

        need_resample = client_sr != s.asr_sample_rate
        last_partial = ""
        t_start = time.perf_counter()

        try:
            while True:
                try:
                    data = await asyncio.wait_for(ws.receive(), timeout=s.ws_receive_timeout)
                except asyncio.TimeoutError:
                    logger.warning("ws_timeout sid=%s", sid)
                    break
                except WebSocketDisconnect:
                    break

                # Control messages (text frames)
                if "text" in data:
                    try:
                        ctrl = json.loads(data["text"])
                    except json.JSONDecodeError:
                        continue
                    if ctrl.get("type") == "finish":
                        final = await asyncio.to_thread(recognizer.finalize)
                        if final and final != last_partial:
                            await ws.send_text(json.dumps({"type": "final", "text": final}))
                        await ws.send_text(json.dumps({"type": "closed"}))
                        break
                    continue

                # Audio frames (binary)
                raw_bytes: bytes = data.get("bytes", b"")
                if not raw_bytes:
                    continue

                samples = _pcm16_to_float32(raw_bytes)
                if need_resample:
                    samples = _resample(samples, client_sr, s.asr_sample_rate)

                interim, is_ep = await asyncio.to_thread(recognizer.accept_waveform, samples)

                if interim and interim != last_partial:
                    last_partial = interim
                    await ws.send_text(json.dumps({"type": "interim", "text": interim}))

                if is_ep and last_partial:
                    final = await asyncio.to_thread(recognizer.get_final_and_reset)
                    if final:
                        await ws.send_text(json.dumps({"type": "final", "text": final}))
                        last_partial = ""

        except Exception as exc:
            logger.exception("ws_error sid=%s: %s", sid, exc)
            try:
                await ws.send_text(json.dumps({"type": "error", "code": "INTERNAL"}))
            except Exception:
                pass
        finally:
            _pool.release(recognizer)
            logger.info("ws_closed sid=%s dur=%.2fs", sid, time.perf_counter() - t_start)
            try:
                await ws.close()
            except Exception:
                pass

    return app


def _pcm16_to_float32(data: bytes) -> np.ndarray:
    n = len(data) // 2
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(data[: n * 2], dtype=np.int16).astype(np.float32) / 32768.0


def _resample(samples: np.ndarray, src: int, dst: int) -> np.ndarray:
    if src == dst or len(samples) == 0:
        return samples
    new_len = max(1, int(len(samples) * dst / src))
    idx = np.linspace(0, len(samples) - 1, new_len)
    return np.interp(idx, np.arange(len(samples)), samples).astype(np.float32)


app = create_app()

if __name__ == "__main__":
    import uvicorn
    cfg = get_asr_server_settings()
    uvicorn.run("asr_server.server:app", host=cfg.asr_server_host, port=cfg.asr_server_port)
