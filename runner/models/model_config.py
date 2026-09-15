from dataclasses import dataclass, field

@dataclass(frozen=True)
class ModelConfig:
    name: str
    provider: str
    model: str
    temperature: float
    max_tokens: int
    context: int
    parameters: dict = field(default_factory=dict)
    supports_tools: bool = False