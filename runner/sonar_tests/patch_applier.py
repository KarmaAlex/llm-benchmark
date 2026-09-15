import re
import subprocess
from pathlib import Path

from runner.models.command_result import PatchResult

class PatchApplier:

    @staticmethod
    def apply(
        project_directory: Path,
        patch: str,
    ) -> PatchResult:
        """
        Apply a unified diff to a project directory.

        The project directory is modified in-place. The caller is responsible
        for providing an isolated copy of the benchmark project.
        """

        cleaned_patch = PatchApplier._clean_patch(patch)

        if not cleaned_patch.strip():
            return PatchResult(
                applied=False,
                output="",
                error="Model returned an empty patch.",
            )

        try:
            result = subprocess.run(
                [
                    "patch",
                    "-p1",
                    "--forward",
                    "--batch",
                ],
                input=cleaned_patch,
                text=True,
                capture_output=True,
                cwd=project_directory,
                check=False,
            )

        except FileNotFoundError:
            return PatchResult(
                applied=False,
                output="",
                error=(
                    "The 'patch' executable was not found. "
                    "Install the patch utility."
                ),
            )

        return PatchResult(
            applied=result.returncode == 0,
            output=result.stdout,
            error=result.stderr if result.returncode != 0 else None,
        )

    @staticmethod
    def _clean_patch(patch: str) -> str:
        """
        Remove Markdown diff fences if the model included them.

        Expected model output:

            ```diff
            --- a/file.java
            +++ b/file.java
            ...
            ```
        """

        patch = patch.strip()

        fenced = re.fullmatch(
            r"```(?:diff)?\s*\n?(.*?)\n?```",
            patch,
            re.DOTALL | re.IGNORECASE,
        )

        if fenced:
            patch = fenced.group(1).strip()

        if not patch.endswith("\n"):
            patch += "\n"

        return patch