import json
from pathlib import Path

from runner.models.benchmark import BenchmarkCase
from runner.filesystem.paths import BENCHMARK_DIR
from runner.filesystem.project_file_loader import ProjectFileLoader

class BenchmarkLoader:
    @staticmethod
    def load(case_directory: Path) -> BenchmarkCase:
        full_path = BENCHMARK_DIR / case_directory
        metadata_path = full_path / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"Missing metadata.json in {full_path}"
            )
        metadata = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )
        file_paths = metadata["files"]
        resources: dict[str, object] = {}
        project_path = None
        for entry in full_path.iterdir():
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
        files: dict[str, str] = {}
        if project_path is None:
            project_path = BENCHMARK_DIR / case_directory
        for file_path in file_paths:
            files[file_path] = ProjectFileLoader.load(project_path, file_path)
        return BenchmarkCase(
            id=case_directory.name,
            project_path=project_path,
            metadata=metadata,
            resources=resources,
            files=files,
        )