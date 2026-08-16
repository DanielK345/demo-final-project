from __future__ import annotations

import threading
from dataclasses import dataclass, field


@dataclass
class TTSMetrics:
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    requests_total: int = 0
    success_total: int = 0
    errors_total: int = 0
    timeout_total: int = 0
    fallback_total: int = 0
    validation_failure_total: int = 0
    queue_rejected_total: int = 0
    cache_hit_total: int = 0
    concurrent_requests: int = 0
    queued_requests: int = 0
    synthesis_seconds_total: float = 0.0
    audio_seconds_total: float = 0.0

    def increment(self, **values: int | float) -> None:
        with self._lock:
            for name, value in values.items():
                setattr(self, name, getattr(self, name) + value)

    def snapshot(self) -> dict[str, int | float]:
        with self._lock:
            return {
                name: value
                for name, value in vars(self).items()
                if name != "_lock" and isinstance(value, (int, float))
            }

    def render_prometheus(self) -> str:
        lines: list[str] = []
        for name, value in self.snapshot().items():
            metric_type = "counter" if name.endswith("_total") else "gauge"
            lines.extend((f"# TYPE alosm_tts_{name} {metric_type}", f"alosm_tts_{name} {value}"))
        return "\n".join(lines) + "\n"

