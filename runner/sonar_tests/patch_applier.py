import re
import subprocess
from pathlib import Path

from runner.models.command_result import PatchResult

# Matches both proper hunk headers ("@@ -12,7 +12,8 @@ optional text") and
# the bare "@@" some models emit without any line numbers.
_HUNK_HEADER = re.compile(r"^@@(?: -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@.*)?\s*$")

# Context lines kept on each side of a hunk's changes, as in `diff -u`.
_MAX_CONTEXT = 3

# GNU patch's default fuzz factor. When one side of a hunk has more than
# this many context lines beyond the other, patch assumes the hunk sits at
# the start or end of the file and won't apply it anywhere else.
_PATCH_FUZZ = 2


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

        normalized_patch = PatchApplier._normalize_hunks(cleaned_patch, project_directory)

        try:
            result = subprocess.run(
                [
                    "patch",
                    "-p1",
                    "--forward",
                    "--batch",
                    "--ignore-whitespace",
                    "--no-backup-if-mismatch",
                ],
                input=normalized_patch,
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

        # `patch` reports hunk failures on stdout and only fatal errors on
        # stderr, so a failure needs both to be diagnosable.
        return PatchResult(
            applied=result.returncode == 0,
            output=result.stdout,
            error=(result.stderr + result.stdout).strip() if result.returncode != 0 else None,
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

    @staticmethod
    def _normalize_hunks(patch: str, project_directory: Path) -> str:
        """
        Rewrite each hunk so that GNU patch judges it on its content rather
        than on bookkeeping models routinely get wrong:

        - hunk headers are recomputed from the hunk body (models miscount
          lines, or emit a bare "@@" with no line numbers at all);
        - the start line is taken from where the hunk's original lines
          actually occur in the target file, when that's unambiguous;
        - context is trimmed to at most 3 lines per side, and to within the
          fuzz factor of the other side (see _PATCH_FUZZ);
        - empty lines inside a hunk are read as blank context lines (models
          often drop the leading space).

        Anything that isn't a hunk (file headers, stray text) passes through
        unchanged for `patch` to judge.
        """
        lines = patch.split("\n")
        if lines and lines[-1] == "":
            lines.pop()

        output: list[str] = []
        target_lines: list[str] | None = None
        line_shift = 0
        index = 0

        while index < len(lines):
            line = lines[index]

            if _is_file_header(lines, index):
                target_lines = _read_target(project_directory, lines[index])
                line_shift = 0
                output += lines[index:index + 2]
                index += 2
                continue

            header = _HUNK_HEADER.match(line)
            if not header:
                output.append(line)
                index += 1
                continue

            index += 1
            body: list[str] = []
            while index < len(lines) and not _HUNK_HEADER.match(lines[index]) and not _is_file_header(lines, index):
                body.append(lines[index])
                index += 1

            body = _trim_context(_clean_body(body))
            old_lines = [l[1:] for l in body if l[:1] in (" ", "-")]
            new_count = sum(1 for l in body if l[:1] in (" ", "+"))

            old_start = _locate(target_lines, old_lines)
            if old_start is None:
                old_start = int(header.group(1)) if header.group(1) else 1
            new_start = old_start + line_shift
            line_shift += new_count - len(old_lines)

            output.append(f"@@ -{old_start},{len(old_lines)} +{new_start},{new_count} @@")
            output += body

        return "\n".join(output) + "\n"


def _is_file_header(lines: list[str], index: int) -> bool:
    # A removed line whose content starts with "-- " also begins with "--- ",
    # so require the "+++ " line to follow.
    return (
        lines[index].startswith("--- ")
        and index + 1 < len(lines)
        and lines[index + 1].startswith("+++ ")
    )


def _read_target(project_directory: Path, old_header: str) -> list[str] | None:
    path = old_header[4:].split("\t")[0].strip()
    if path == "/dev/null":
        return None
    # Mirror `patch -p1`: drop the leading "a/".
    relative = path.split("/", 1)[1] if "/" in path else path
    file_path = project_directory / relative
    if not file_path.is_file():
        return None
    return file_path.read_text(encoding="utf-8").split("\n")


def _clean_body(body: list[str]) -> list[str]:
    # Trailing empty lines separate hunks rather than belong to them.
    while body and body[-1] == "":
        body.pop()
    return [" " if line == "" else line for line in body]


def _trim_context(body: list[str]) -> list[str]:
    changed = [i for i, line in enumerate(body) if line[:1] in ("+", "-")]
    # A "\ No newline at end of file" marker belongs to the line before it;
    # leave such hunks alone rather than risk separating the two.
    if not changed or any(line.startswith("\\") for line in body):
        return body

    leading = changed[0]
    trailing = len(body) - 1 - changed[-1]
    keep_leading = min(leading, _MAX_CONTEXT, trailing + _PATCH_FUZZ)
    keep_trailing = min(trailing, _MAX_CONTEXT, leading + _PATCH_FUZZ)

    return body[leading - keep_leading:changed[-1] + 1 + keep_trailing]


def _locate(target_lines: list[str] | None, old_lines: list[str]) -> int | None:
    """1-based line where `old_lines` occur in the target, ignoring
    whitespace like `patch --ignore-whitespace` does; None unless there is
    exactly one such place."""
    if not target_lines or not old_lines:
        return None

    def squash(text: str) -> str:
        return "".join(text.split())

    wanted = [squash(line) for line in old_lines]
    haystack = [squash(line) for line in target_lines]
    starts = [
        start for start in range(len(haystack) - len(wanted) + 1)
        if haystack[start:start + len(wanted)] == wanted
    ]
    return starts[0] + 1 if len(starts) == 1 else None
