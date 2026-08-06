from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    suite: str
    metadata: dict
    issue: dict
    rule_text: str
    project_path: Path
    case_path: Path