from dataclasses import dataclass

@dataclass(frozen=True)
class Prompt:
    version: str
    system: str
    user: str