"""Per-session streaming recognizer wrapping sherpa_onnx.OnlineRecognizer."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any

import numpy as np

from .config import ASRServerSettings, get_asr_server_settings

logger = logging.getLogger(__name__)


class StreamingRecognizer:
    """One recognizer stream per call session."""

    def __init__(self, pool_recognizer: Any, settings: ASRServerSettings) -> None:
        self._rec = pool_recognizer
        self._settings = settings
        self._stream = pool_recognizer.create_stream()
        self._lock = threading.Lock()

    def accept_waveform(self, samples: np.ndarray) -> tuple[str, bool]:
        """Feed PCM float32 samples. Returns (partial_text, is_endpoint)."""
        with self._lock:
            self._stream.accept_waveform(self._settings.asr_sample_rate, samples)
            while self._rec.is_ready(self._stream):
                self._rec.decode(self._stream)
            result = self._rec.get_result(self._stream)
            text = result.text.strip() if result else ""
            is_ep = self._rec.is_endpoint(self._stream) if text else False
            return text, is_ep

    def get_final_and_reset(self) -> str:
        """Get final text and reset stream for next utterance."""
        with self._lock:
            result = self._rec.get_result(self._stream)
            text = result.text.strip() if result else ""
            self._rec.reset(self._stream)
            return text

    def finalize(self) -> str:
        """Feed silence to flush remaining audio, return last text."""
        with self._lock:
            silence = np.zeros(int(self._settings.asr_sample_rate * 0.5), dtype=np.float32)
            self._stream.accept_waveform(self._settings.asr_sample_rate, silence)
            while self._rec.is_ready(self._stream):
                self._rec.decode(self._stream)
            result = self._rec.get_result(self._stream)
            return result.text.strip() if result else ""


class RecognizerPool:
    """Shared model, per-session streams."""

    def __init__(self, settings: ASRServerSettings | None = None) -> None:
        self._settings = settings or get_asr_server_settings()
        self._recognizer: Any | None = None
        self._ready = False
        self._active_count = 0
        self._total_sessions = 0
        self._errors = 0
        self._lock = threading.Lock()

    @property
    def ready(self) -> bool:
        return self._ready and self._recognizer is not None

    @property
    def active_count(self) -> int:
        return self._active_count

    def load(self) -> None:
        """Load model — blocking, call in thread."""
        s = self._settings
        files = {
            "encoder": s.model_path(s.asr_encoder_path),
            "decoder": s.model_path(s.asr_decoder_path),
            "joiner": s.model_path(s.asr_joiner_path),
            "tokens": s.model_path(s.asr_tokens_path),
        }
        missing = [n for n, p in files.items() if not p.is_file()]
        if missing:
            raise FileNotFoundError(f"Missing ASR model files: {missing}")

        import sherpa_onnx

        t0 = time.perf_counter()
        self._recognizer = sherpa_onnx.OnlineRecognizer.from_transducer(
            tokens=str(files["tokens"]),
            encoder=str(files["encoder"]),
            decoder=str(files["decoder"]),
            joiner=str(files["joiner"]),
            num_threads=s.asr_num_threads,
            sample_rate=s.asr_sample_rate,
            feature_dim=s.asr_feature_dim,
            enable_endpoint_detection=True,
            rule1_min_trailing_silence=s.endpoint_rule1_silence,
            rule2_min_trailing_silence=s.endpoint_rule2_silence,
            rule3_min_utterance_length=s.endpoint_rule3_length,
            decoding_method="greedy_search",
            model_type="zipformer2",
            provider=s.sherpa_provider,
        )
        # Warm-up
        ws = self._recognizer.create_stream()
        silence = np.zeros(s.asr_sample_rate, dtype=np.float32)
        ws.accept_waveform(s.asr_sample_rate, silence)
        while self._recognizer.is_ready(ws):
            self._recognizer.decode(ws)
        self._ready = True
        logger.info("OnlineRecognizer ready in %.2fs", time.perf_counter() - t0)

    def acquire(self) -> StreamingRecognizer | None:
        if not self.ready:
            return None
        with self._lock:
            if self._active_count >= self._settings.asr_max_concurrent_sessions:
                return None
            self._active_count += 1
            self._total_sessions += 1
        return StreamingRecognizer(self._recognizer, self._settings)

    def release(self, _recognizer: StreamingRecognizer) -> None:
        with self._lock:
            self._active_count = max(0, self._active_count - 1)

    def shutdown(self) -> None:
        self._ready = False
        self._recognizer = None

    def prometheus_metrics(self) -> str:
        lines = [
            f"asr_active_sessions {self._active_count}",
            f"asr_total_sessions_total {self._total_sessions}",
            f"asr_errors_total {self._errors}",
            f"asr_model_ready {1 if self._ready else 0}",
        ]
        return "\n".join(lines) + "\n"
