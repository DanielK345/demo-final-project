from dataclasses import dataclass


@dataclass(slots=True)
class WorkerConfig:
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/1"


worker_config = WorkerConfig()
