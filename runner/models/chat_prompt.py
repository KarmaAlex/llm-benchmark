from dataclasses import dataclass

@dataclass(frozen=True)
class ChatPrompt:
    messages: list[dict]
    version: str