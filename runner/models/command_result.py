from dataclasses import dataclass

@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    execution_time: float
    @property
    def success(self) -> bool:
        return self.return_code == 0

@dataclass(frozen=True)
class PatchResult:
    applied: bool
    output: str
    error: str | None

@dataclass(frozen=True)
class CompilationResult:
    compiled: bool
    command: list[str]
    stdout: str
    stderr: str
    execution_time: float