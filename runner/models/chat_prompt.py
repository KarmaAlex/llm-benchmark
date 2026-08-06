from dataclasses import dataclass
from openai.types.chat import ChatCompletionMessageParam

@dataclass(frozen=True)
class ChatPrompt:
    version: str
    messages: list[ChatCompletionMessageParam]