import json
from pathlib import Path

from runner.models.benchmark import BenchmarkCase


class BenchmarkLoader:
    @staticmethod
    def load(case_directory: Path) -> BenchmarkCase:
        metadata_path = case_directory / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Missing metadata.json in {case_directory}"
            )
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
        resources: dict[str, object] = {}
        project_path = None
        for entry in case_directory.iterdir():
            if entry.name == "metadata.json":
                continue
            if entry.is_dir():
                if entry.name == "project":
                    project_path = entry
                continue
            key = entry.stem
            if entry.suffix == ".json":
                resources[key] = json.loads(
                    entry.read_text(encoding="utf-8")
                )
            else:
                resources[key] = entry.read_text(
                    encoding="utf-8"
                )
        return BenchmarkCase(
            id=case_directory.name,
            suite=case_directory.parent.name,
            case_path=case_directory,
            project_path=project_path,
            metadata=metadata,
            resources=resources,
        )