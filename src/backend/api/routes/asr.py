from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from src.voice.asr.zipformer.config import get_zipformer_settings
from src.voice.asr.zipformer.errors import ASRErrorCode, ZipformerASRError
from src.voice.asr.zipformer.schemas import ErrorDetail, ErrorResponse, TranscriptionResponse
from src.voice.asr.zipformer.service import get_zipformer_service

logger = logging.getLogger(__name__)
router = APIRouter(tags=["asr"])


def _error(request_id: str, exc: ZipformerASRError) -> JSONResponse:
    payload = ErrorResponse(error=ErrorDetail(code=exc.code, message=str(exc), request_id=request_id))
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump(mode="json"))


@router.get("/health/live")
async def asr_liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready")
async def asr_readiness() -> Response:
    service = get_zipformer_service()
    payload = {
        "status": "ready" if service.ready else "not_ready",
        "model_state": service.runtime.state,
        "failure_reason": service.runtime.failure_reason,
    }
    return JSONResponse(status_code=200 if service.ready else 503, content=payload)


@router.get("/metrics")
async def asr_metrics() -> Response:
    return Response(get_zipformer_service().metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


@router.post(
    "/v1/audio/transcriptions",
    response_model=TranscriptionResponse,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def transcribe_audio(request: Request, file: UploadFile = File(...)) -> TranscriptionResponse | JSONResponse:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    settings = get_zipformer_settings()
    try:
        data = await file.read(settings.max_audio_size_mb * 1024 * 1024 + 1)
        result = await get_zipformer_service().transcribe_upload(
            data,
            filename=file.filename or "audio",
            mime_type=file.content_type or "application/octet-stream",
        )
    except ZipformerASRError as exc:
        logger.warning("ASR request failed request_id=%s code=%s", request_id, exc.code)
        return _error(request_id, exc)
    except Exception as exc:
        logger.exception("Unexpected ASR request failure request_id=%s error_type=%s", request_id, type(exc).__name__)
        return _error(
            request_id,
            ZipformerASRError(ASRErrorCode.INFERENCE_FAILED, "ASR request failed", status_code=500),
        )
    logger.info(
        "ASR request succeeded request_id=%s audio_duration_ms=%s queue_wait_ms=%s "
        "preprocessing_ms=%s inference_ms=%s processing_ms=%s realtime_factor=%s",
        request_id,
        result.audio_duration_ms,
        result.queue_wait_ms,
        result.preprocessing_ms,
        result.inference_ms,
        result.processing_ms,
        result.realtime_factor,
    )
    return TranscriptionResponse(
        text=result.text,
        confidence=result.confidence,
        audio_duration_ms=result.audio_duration_ms,
        queue_wait_ms=result.queue_wait_ms,
        preprocessing_ms=result.preprocessing_ms,
        inference_ms=result.inference_ms,
        processing_ms=result.processing_ms,
        realtime_factor=result.realtime_factor,
        request_id=request_id,
        model=settings.asr_model_id,
    )
