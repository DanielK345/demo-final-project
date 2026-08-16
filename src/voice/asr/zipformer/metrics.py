from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class ASRMetrics:
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    requests_total: int = 0
    success_total: int = 0
    errors_total: int = 0
    queue_rejected_total: int = 0
    concurrent_requests: int = 0
    queue_depth: int = 0
    model_ready: int = 0
    audio_seconds_total: float = 0.0
    queue_wait_seconds_total: float = 0.0
    preprocessing_seconds_total: float = 0.0
    inference_seconds_total: float = 0.0
    request_seconds_total: float = 0.0
    realtime_factor_sum: float = 0.0

    def update(self, **values: float | int) -> None:
        with self._lock:
            for name, value in values.items():
                setattr(self, name, value)

    def increment(self, **values: float | int) -> None:
        with self._lock:
            for name, value in values.items():
                setattr(self, name, getattr(self, name) + value)

    def render_prometheus(self) -> str:
        with self._lock:
            values = {
                name: value for name, value in vars(self).items() if name != "_lock" and isinstance(value, (int, float))
            }
        lines = ["# TYPE alosm_asr_info gauge", 'alosm_asr_info{runtime="sherpa-onnx"} 1']
        for name, value in values.items():
            metric_type = "counter" if name.endswith(("_total", "_sum")) else "gauge"
            lines.extend((f"# TYPE alosm_asr_{name} {metric_type}", f"alosm_asr_{name} {value}"))
        return "\n".join(lines) + "\n"
