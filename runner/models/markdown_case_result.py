from dataclasses import dataclass


@dataclass
class MarkdownCaseResult:
    case_id: str
    difficulty: int | None
    matched: bool
    execution_time: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    tokens_per_second: float = 0.0
    gpu_memory_mb: float | None = None
    finish_reason: str | None = None
    error: str | None = None
    response_text: str | None = None
    parsed_output: object = None
