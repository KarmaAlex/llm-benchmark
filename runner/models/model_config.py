from dataclasses import dataclass

@dataclass(frozen=True)
class ModelConfig:
    name: str
    provider: str
    temperature: float
    max_tokens: int
    context: int
    seed: int | None = None