from dataclasses import dataclass
from typing import Any


@dataclass
class MarkdownResult:
    prompt: str = ""
    raw_response: dict | None = None
    response_text: str | None = None
    parsed_output: Any = None
    expected_output: Any = None
    parse_error: str | None = None
    matched: bool = False
    execution_time: float = 0
    input_tokens: int = 0
    output_tokens: int = 0
