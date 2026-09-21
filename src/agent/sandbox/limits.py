from __future__ import annotations

from pydantic import BaseModel

MIN_TIMEOUT_SECONDS = 5


class ResourceLimits(BaseModel):
    memory_mb: int = 512
    cpu_cores: float = 1.0
    pids_limit: int = 128
    timeout_seconds: int = 30

    @property
    def memory_bytes(self) -> int:
        return self.memory_mb * 1024 * 1024

    @property
    def nano_cpus(self) -> int:
        return int(self.cpu_cores * 1_000_000_000)


DEFAULT_LIMITS = ResourceLimits()


def limits_from_contract_seconds(max_execution_seconds: int) -> ResourceLimits:
    return ResourceLimits(timeout_seconds=max(max_execution_seconds, MIN_TIMEOUT_SECONDS))
