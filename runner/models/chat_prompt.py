from dataclasses import dataclass
from typing import Any
from openai.types.chat import ChatCompletionMessageParam

@dataclass(frozen=True)
class ChatPrompt:
    version: str
    messages: list[ChatCompletionMessageParam]
    tools: list[dict[str, Any]] | None = None