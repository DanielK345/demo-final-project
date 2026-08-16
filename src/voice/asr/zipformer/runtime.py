from __future__ import annotations

import enum
import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.voice.asr.zipformer.config import ZipformerSettings
from src.voice.asr.zipformer.errors import ASRErrorCode, ZipformerASRError

logger = logging.getLogger(__name__)


class ModelState(enum.StrEnum):
    STOPPED = "STOPPED"
    LOADING_MODEL = "LOADING_MODEL"
    WARMING_UP = "WARMING_UP"
    READY = "READY"
    MODEL_FAILED = "MODEL_FAILED"


@dataclass(frozen=True)
class RuntimeResult:
    text: str
    confidence: float | None
    inference_ms: int


class ZipformerRuntime:
    def __init__(self, settings: ZipformerSettings) -> None:
        self.settings = settings
        self.state = ModelState.STOPPED
        self.failure_reason: str | None = None
        self._recognizer: Any | None = None
        self._state_lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self.state is ModelState.READY and self._recognizer is not None

    def load_and_warm(self) -> None:
        with self._state_lock:
            if self.ready:
                return
            self.state = ModelState.LOADING_MODEL
            self.failure_reason = None
        try:
            files = self.settings.required_model_files
            missing = [name for name, path in files.items() if not path.is_file()]
            if missing:
                raise FileNotFoundError(f"missing model files: {', '.join(missing)}")
            import sherpa_onnx

            recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=str(files["encoder"]),
                decoder=str(files["decoder"]),
                joiner=str(files["joiner"]),
                tokens=str(files["tokens"]),
                num_threads=self.settings.asr_num_threads,
                sample_rate=self.settings.asr_sample_rate,
                feature_dim=self.settings.asr_feature_dim,
                decoding_method="greedy_search",
                provider="cpu",
            )
            self._recognizer = recognizer
            self.state = ModelState.WARMING_UP
            self.transcribe(np.zeros(self.settings.asr_sample_rate, dtype=np.float32), allow_warming=True)
            self.state = ModelState.READY
            logger.info("ZipFormer ASR model loaded and warmed model=%s", self.settings.asr_model_id)
        except Exception as exc:
            self._recognizer = None
            self.state = ModelState.MODEL_FAILED
            self.failure_reason = type(exc).__name__
            logger.exception("ZipFormer model initialization failed error_type=%s", type(exc).__name__)
            raise

    def transcribe(self, samples: np.ndarray, *, allow_warming: bool = False) -> RuntimeResult:
        if self._recognizer is None or (not self.ready and not allow_warming):
            raise ZipformerASRError(ASRErrorCode.MODEL_UNAVAILABLE, "ASR model is not ready", status_code=503)
        started = time.perf_counter()
        try:
            stream = self._recognizer.create_stream()
            stream.accept_waveform(self.settings.asr_sample_rate, samples)
            self._recognizer.decode_stream(stream)
            result = stream.result
            text = result.text.strip()
            log_probs = list(getattr(result, "ys_log_probs", ()) or ())
            confidence = math.exp(sum(log_probs) / len(log_probs)) if log_probs else None
            if confidence is not None:
                confidence = max(0.0, min(1.0, confidence))
        except Exception as exc:
            raise ZipformerASRError(ASRErrorCode.INFERENCE_FAILED, "ASR inference failed", status_code=500) from exc
        return RuntimeResult(
            text=text,
            confidence=confidence,
            inference_ms=round((time.perf_counter() - started) * 1000),
        )
