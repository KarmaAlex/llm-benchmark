from dataclasses import dataclass

@dataclass
class ExecutionResult:
    prompt: str = ""
    raw_response: dict | None = None
    response_text: str | None = None
    patch: str | None = None
    patch_applied: bool = False
    compiled: bool = False
    tests_passed: bool = False
    sonar_before: dict | None = None
    sonar_after: dict | None = None
    execution_time: float = 0
    input_tokens: int = 0
    output_tokens: int = 0