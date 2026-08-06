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