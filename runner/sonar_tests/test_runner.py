import re
import subprocess
import time
from pathlib import Path

from runner.models.command_result import TestExecutionResult

SUMMARY_PATTERN = re.compile(
    r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)"
)


class TestRunner:

    @staticmethod
    def run(
        project_directory: Path,
        timeout: float = 300,
    ) -> TestExecutionResult:
        command = TestRunner._detect_command(
            project_directory
        )
        if command is None:
            return TestExecutionResult(
                ran=False,
                passed=False,
                tests_run=0,
                failures=0,
                errors=0,
                skipped=0,
                command=[],
                stdout="",
                stderr="No supported build system found.",
                execution_time=0.0,
            )
        start = time.perf_counter()
        try:
            result = subprocess.run(
                command,
                cwd=project_directory,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            execution_time = time.perf_counter() - start
            stdout = TestRunner._decode_output(exc.stdout)
            stderr = TestRunner._decode_output(exc.stderr)
            return TestExecutionResult(
                ran=False,
                passed=False,
                tests_run=0,
                failures=0,
                errors=0,
                skipped=0,
                command=command,
                stdout=stdout,
                stderr=f"{stderr}\nTest execution timed out.",
                execution_time=execution_time,
            )
        execution_time = time.perf_counter() - start

        tests_run, failures, errors, skipped = TestRunner._parse_summary(result.stdout)
        ran = tests_run > 0

        return TestExecutionResult(
            ran=ran,
            passed=ran and result.returncode == 0 and failures == 0 and errors == 0,
            tests_run=tests_run,
            failures=failures,
            errors=errors,
            skipped=skipped,
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
            execution_time=execution_time,
        )

    @staticmethod
    def _parse_summary(stdout: str) -> tuple[int, int, int, int]:
        # Surefire prints a per-test-class line ("... -- in some.ClassName") for
        # every class, then a final aggregate line under "Results:" with the same
        # shape but no class suffix. Only the aggregate line(s) should be summed,
        # otherwise every class's count would be counted twice.
        tests_run = failures = errors = skipped = 0
        for line in stdout.splitlines():
            if "Time elapsed" in line:
                continue
            match = SUMMARY_PATTERN.search(line)
            if match:
                tests_run += int(match.group(1))
                failures += int(match.group(2))
                errors += int(match.group(3))
                skipped += int(match.group(4))
        return tests_run, failures, errors, skipped

    @staticmethod
    def _decode_output(
        output: str | bytes | None,
    ) -> str:
        if output is None:
            return ""
        if isinstance(output, bytes):
            return output.decode(
                "utf-8",
                errors="replace",
            )
        return output

    @staticmethod
    def _detect_command(
        project_directory: Path,
    ) -> list[str] | None:
        if (project_directory / "mvnw").exists():
            return [
                "./mvnw",
                "test",
            ]
        if (project_directory / "pom.xml").exists():
            return [
                "mvn",
                "test",
            ]
        return None
