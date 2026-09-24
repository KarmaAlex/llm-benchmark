import json
from datetime import datetime, timezone
from pathlib import Path

from runner.filesystem.paths import RESULTS_DIR

REPORT_FILE_NAME = "report.json"


class ResultsManager:

    @staticmethod
    def create_run_directory():
        timestamp = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        path = RESULTS_DIR / timestamp
        path.mkdir(parents=True)
        return path

    @staticmethod
    def resolve_run_directory(run_id: str) -> Path:
        """Accept either a path to a run directory or its name under results/."""
        candidate = Path(run_id)
        if candidate.is_dir():
            return candidate

        candidate = RESULTS_DIR / run_id
        if candidate.is_dir():
            return candidate

        raise FileNotFoundError(
            f"No run directory found for '{run_id}' (looked for it directly and under {RESULTS_DIR})"
        )

    @staticmethod
    def load_report(run_directory: Path) -> dict:
        report_path = run_directory / REPORT_FILE_NAME
        if not report_path.exists():
            raise FileNotFoundError(f"No {REPORT_FILE_NAME} found in {run_directory}")
        return json.loads(report_path.read_text(encoding="utf-8"))

    @staticmethod
    def write_report(run_directory: Path, report: dict) -> Path:
        report_path = run_directory / REPORT_FILE_NAME
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report_path
