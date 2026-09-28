from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ModelResponse:
    content: str
    latency: float
    prompt_tokens: int
    completion_tokens: int
    finish_reason: str | None
    raw: dict[str,Any]
    tool_calls: list[dict[str, Any]] | None = None
    gpu_memory_mb: float | None = None
    # Mean / peak power over the call and the energy it drew (GPU board +
    # CPU package; see runner/providers/power.py). None when not measured.
    gpu_power_w: float | None = None
    gpu_power_peak_w: float | None = None
    cpu_power_w: float | None = None
    cpu_power_peak_w: float | None = None
    energy_wh: float | None = None
    # Other sizeable compute processes on the GPU when the call ended; any
    # means another job shared it (power, memory and latency are then
    # partly someone else's). None when it couldn't be told.
    gpu_other_processes: int | None = None
    # Backend build identifier reported by OpenAI; a change between two
    # otherwise identical requests explains a changed response.
    system_fingerprint: str | None = None