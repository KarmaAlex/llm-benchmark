from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    suite: str
    case_path: Path
    project_path: Path | None
    resources: dict[str, Any]
    metadata: dict