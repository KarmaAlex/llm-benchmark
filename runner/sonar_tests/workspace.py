import shutil
from pathlib import Path

class Workspace:

    @staticmethod
    def create(
        source: Path | None,
        destination: Path,
    ) -> Path:
        if destination.exists():
            raise FileExistsError(f"Workspace already exists: {destination}")
        if source is not None:
            shutil.copytree(
                source,
                destination,
            )
        else:
            raise FileExistsError(f"Source path is null or doesn't exist: {source}")
        return destination