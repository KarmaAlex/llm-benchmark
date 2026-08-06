from typing import Literal, TypedDict

Role = Literal["system", "user"]

class ChatMessage(TypedDict):
    role: Role
    content: str