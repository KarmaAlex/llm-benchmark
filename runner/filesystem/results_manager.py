from datetime import datetime, timezone
from pathlib import Path

from runner.filesystem.paths import RESULTS_DIR


class ResultsManager:

    @staticmethod
    def create_run_directory():
        timestamp = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d_%H-%M-%S"
        )
        path = RESULTS_DIR / timestamp
        path.mkdir(parents=True)
        return path