from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    project_path: Path | None
    resources: dict[str, Any]
    files: dict[str, Any]
    metadata: dict